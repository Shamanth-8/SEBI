"""
Train the local RegGraph models on the synthetic SEBI corpus.

Six estimators are fitted and persisted to data/models/:

  sentence level (input = one sentence)
    obligation_clf     binary   is this sentence an obligation?
    severity_clf       3-class  high / medium / low
    category_clf       5-class  regulatory theme
    deadline_clf       4-class  fixed / recurring / relative / not_specified
    intermediary_clf   multi-label  which intermediary types it binds

  document level (input = a ~1200 char window, averaged over the document)
    doc_kind_clf       binary   SEBI circular vs. any other document
    doc_family_clf     5-class  which circular family it resembles
    family_centroids   TF-IDF centroid per family, for novelty detection

Honest evaluation: because the corpus is generated from a template bank, a random
split would leak phrasing between train and test and report ~100%. The headline
score is therefore measured on HELD-OUT TEMPLATES — sentence patterns the model
never saw during fitting — which is the number that actually predicts behaviour
on a real circular.
"""
from __future__ import annotations

import json
import logging
import random
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_recall_fscore_support
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import MultiLabelBinarizer

from app.ml import corpus as C
from app.ml.features import ModalityFeatures
from app.ml.textutil import split_sentences

logger = logging.getLogger(__name__)

MODEL_DIR = Path("data/models")
MODEL_VERSION = "1.0.0"


# ── Feature extraction ───────────────────────────────────────────────────────

def _sentence_features(min_df: int = 2, modality: bool = False) -> FeatureUnion:
    """
    Views of a sentence:
      word n-grams  — regulatory phrasing ("shall submit", "within thirty days")
      char n-grams  — robustness to the spacing/hyphenation noise pdfplumber leaves
      modality      — deontic verbs, bound party, timeline, and the structural
                      signatures of contents lists and tables (see features.py)

    The modality block is what carries the detector across the gap from synthetic
    training text to a real 38-page master circular. It is used ONLY for the
    obligation detector: for the semantic heads (severity / category) it is
    uninformative and measurably dilutes accuracy on held-out templates.
    """
    blocks = [
        ("word", TfidfVectorizer(
            ngram_range=(1, 3), sublinear_tf=True, min_df=min_df,
            strip_accents="unicode", lowercase=True, max_features=60000,
        )),
        ("char", TfidfVectorizer(
            analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True,
            min_df=min_df, lowercase=True, max_features=60000,
        )),
    ]
    if modality:
        blocks.append(("modality", ModalityFeatures()))
    return FeatureUnion(blocks)


def _make_clf(features: FeatureUnion, **lr_kwargs) -> Pipeline:
    params = dict(max_iter=2000, C=4.0, class_weight="balanced")
    params.update(lr_kwargs)
    return Pipeline([("feats", features), ("clf", LogisticRegression(**params))])


# ── Dataset construction ─────────────────────────────────────────────────────

class SentenceRow(dict):
    """One labelled training sentence."""


def build_sentence_dataset(specs: List[C.CircularSpec]) -> List[SentenceRow]:
    """
    Flatten circular specs into labelled sentences.

    Labels come from the spec (ground truth by construction). Preamble, closing
    and letterhead lines are emitted as negatives so the model learns to reject
    recitals — the single biggest source of false positives on real circulars.
    """
    rows: List[SentenceRow] = []
    for spec in specs:
        doc_id = spec.circular_id

        for c in spec.all_clauses:
            for sent in split_sentences(c.text):
                rows.append(SentenceRow(
                    text=sent,
                    doc_id=doc_id,
                    family=spec.family,
                    is_obligation=int(c.is_obligation),
                    severity=c.severity if c.is_obligation else "",
                    category=c.category if c.is_obligation else "",
                    deadline_type=c.deadline_type if c.is_obligation else "",
                    intermediaries=c.intermediaries if c.is_obligation else [],
                    template_id=c.template_id or f"ctx#{spec.family}",
                ))

        # Recitals / closing / boilerplate → negatives
        boiler = list(spec.preamble) + list(spec.closing) + [
            f"Sub: {spec.subject}",
            "Madam / Sir,",
            "Yours faithfully,",
            "General Manager",
            spec.reference,
            "SECURITIES AND EXCHANGE BOARD OF INDIA",
        ] + list(spec.addressees)
        for para in boiler:
            for sent in split_sentences(para):
                rows.append(SentenceRow(
                    text=sent, doc_id=doc_id, family=spec.family,
                    is_obligation=0, severity="", category="",
                    deadline_type="", intermediaries=[],
                    template_id=f"ctx#{spec.family}",
                ))

    # Structural noise — contents entries, abbreviation tables, definitions,
    # cross-references. Spread across synthetic doc ids so the document-grouped
    # split keeps some on each side.
    noise = C.build_structural_noise()
    for i, line in enumerate(noise):
        rows.append(SentenceRow(
            text=line, doc_id=f"__noise_{i % 5}", family="_noise",
            is_obligation=0, severity="", category="", deadline_type="",
            intermediaries=[], template_id="ctx#noise",
        ))
    return rows


def build_document_dataset(
    specs: List[C.CircularSpec],
    negatives: List[Tuple[str, str]],
    window: int = 1200,
) -> Tuple[List[str], List[int], List[str]]:
    """
    Sliding windows over each document.

    Windows (rather than whole documents) give the document classifier enough
    samples to fit, and at inference the per-window probabilities are averaged —
    which also makes the confidence score meaningful for long PDFs.
    """
    texts: List[str] = []
    is_circular: List[int] = []
    family: List[str] = []

    def add_windows(text: str, circ: int, fam: str):
        text = " ".join(text.split())
        if not text:
            return
        step = max(window // 2, 200)
        for start in range(0, max(len(text) - window // 2, 1), step):
            chunk = text[start:start + window]
            if len(chunk) < 250:
                continue
            texts.append(chunk)
            is_circular.append(circ)
            family.append(fam)

    for spec in specs:
        add_windows(spec.to_text(), 1, spec.family)
    for name, text in negatives:
        add_windows(text, 0, "not_a_circular")

    return texts, is_circular, family


# ── Evaluation ───────────────────────────────────────────────────────────────

def _template_holdout_split(rows: List[SentenceRow], holdout_frac: float = 0.3,
                            seed: int = 7) -> Tuple[List[int], List[int]]:
    """Split sentence indices so that no *template* appears on both sides."""
    rng = random.Random(seed)
    templates = sorted({r["template_id"] for r in rows if r["is_obligation"]})
    rng.shuffle(templates)
    n_hold = max(1, int(len(templates) * holdout_frac))
    held = set(templates[:n_hold])

    # Negatives are split by document so the test side still has recitals to reject.
    docs = sorted({r["doc_id"] for r in rows})
    rng.shuffle(docs)
    held_docs = set(docs[:max(1, int(len(docs) * holdout_frac))])

    train_idx, test_idx = [], []
    for i, r in enumerate(rows):
        if r["is_obligation"]:
            (test_idx if r["template_id"] in held else train_idx).append(i)
        else:
            (test_idx if r["doc_id"] in held_docs else train_idx).append(i)
    return train_idx, test_idx


def _eval_binary(rows, train_idx, test_idx) -> Dict:
    X_tr = [rows[i]["text"] for i in train_idx]
    y_tr = [rows[i]["is_obligation"] for i in train_idx]
    X_te = [rows[i]["text"] for i in test_idx]
    y_te = [rows[i]["is_obligation"] for i in test_idx]
    if len(set(y_tr)) < 2 or not X_te:
        return {}
    model = _make_clf(_sentence_features(min_df=1, modality=True)).fit(X_tr, y_tr)
    pred = model.predict(X_te)
    p, r, f, _ = precision_recall_fscore_support(y_te, pred, average="binary",
                                                 zero_division=0)
    return {
        "precision": round(float(p), 4),
        "recall": round(float(r), 4),
        "f1": round(float(f), 4),
        "n_train": len(X_tr),
        "n_test": len(X_te),
        "test_positives": int(sum(y_te)),
    }


def _eval_multiclass(rows, train_idx, test_idx, key: str) -> Dict:
    tr = [(rows[i]["text"], rows[i][key]) for i in train_idx
          if rows[i]["is_obligation"] and rows[i][key]]
    te = [(rows[i]["text"], rows[i][key]) for i in test_idx
          if rows[i]["is_obligation"] and rows[i][key]]
    if len(tr) < 10 or not te or len({y for _, y in tr}) < 2:
        return {}
    model = _make_clf(_sentence_features(min_df=1)).fit([t for t, _ in tr], [y for _, y in tr])
    pred = model.predict([t for t, _ in te])
    true = [y for _, y in te]
    return {
        "accuracy": round(float(np.mean([a == b for a, b in zip(pred, true)])), 4),
        "macro_f1": round(float(f1_score(true, pred, average="macro", zero_division=0)), 4),
        "n_train": len(tr),
        "n_test": len(te),
    }


# ── Training entry point ─────────────────────────────────────────────────────

def train_all(
    model_dir: Path = MODEL_DIR,
    n_per_family: int = 6,
    seed: int = 4242,
    verbose: bool = True,
) -> Dict:
    """Fit every estimator, persist them, and return the model card."""
    import joblib

    model_dir = Path(model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    def say(msg: str):
        if verbose:
            print(msg)

    # ── Corpus ────────────────────────────────────────────────────────────
    demo_specs = C.build_demo_corpus()
    aug_specs = C.build_training_specs(n_per_family=n_per_family, seed=seed)
    all_specs = demo_specs + aug_specs
    negatives = C.build_negative_documents(n=8)

    rows = build_sentence_dataset(all_specs)
    say(f"Corpus: {len(all_specs)} circulars ({len(demo_specs)} demo + {len(aug_specs)} augmented), "
        f"{len(rows)} labelled sentences, {sum(r['is_obligation'] for r in rows)} obligations")

    # ── Honest generalisation score on unseen templates ───────────────────
    tr_idx, te_idx = _template_holdout_split(rows)
    say(f"Held-out-template evaluation: {len(tr_idx)} train / {len(te_idx)} test sentences")
    evaluation = {
        "protocol": "held-out templates (obligation phrasings never seen in training) "
                    "+ held-out documents for negatives",
        "obligation_clf": _eval_binary(rows, tr_idx, te_idx),
        "severity_clf": _eval_multiclass(rows, tr_idx, te_idx, "severity"),
        "category_clf": _eval_multiclass(rows, tr_idx, te_idx, "category"),
        "deadline_clf": _eval_multiclass(rows, tr_idx, te_idx, "deadline_type"),
    }
    for k, v in evaluation.items():
        if isinstance(v, dict) and v:
            say(f"  {k:16} {v}")

    # ── Fit final models on the full corpus ───────────────────────────────
    texts = [r["text"] for r in rows]
    y_obl = [r["is_obligation"] for r in rows]

    say("Fitting obligation_clf …")
    obligation_clf = _make_clf(_sentence_features(modality=True)).fit(texts, y_obl)

    obl_rows = [r for r in rows if r["is_obligation"]]
    obl_texts = [r["text"] for r in obl_rows]

    say("Fitting severity_clf …")
    severity_clf = _make_clf(_sentence_features()).fit(obl_texts, [r["severity"] for r in obl_rows])

    say("Fitting category_clf …")
    category_clf = _make_clf(_sentence_features()).fit(obl_texts, [r["category"] for r in obl_rows])

    say("Fitting deadline_clf …")
    deadline_clf = _make_clf(_sentence_features()).fit(
        obl_texts, [r["deadline_type"] for r in obl_rows])

    say("Fitting intermediary_clf (multi-label) …")
    mlb = MultiLabelBinarizer(classes=C.INTERMEDIARY_TYPES)
    Y = mlb.fit_transform([r["intermediaries"] for r in obl_rows])
    # Drop labels with a single class present — OneVsRest cannot fit those.
    keep = [j for j in range(Y.shape[1]) if len(set(Y[:, j])) > 1]
    intermediary_clf = Pipeline([
        ("feats", _sentence_features()),
        ("clf", OneVsRestClassifier(LogisticRegression(max_iter=2000, C=4.0,
                                                       class_weight="balanced"))),
    ]).fit(obl_texts, Y[:, keep])
    intermediary_labels = [mlb.classes_[j] for j in keep]

    # ── Document-level ────────────────────────────────────────────────────
    say("Fitting document-level models …")
    doc_texts, doc_is_circ, doc_family = build_document_dataset(all_specs, negatives)

    doc_features = FeatureUnion([
        ("word", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=2,
                                 strip_accents="unicode", max_features=40000)),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5),
                                 sublinear_tf=True, min_df=2, max_features=40000)),
    ])
    doc_kind_clf = Pipeline([
        ("feats", doc_features),
        ("clf", LogisticRegression(max_iter=2000, C=4.0, class_weight="balanced")),
    ]).fit(doc_texts, doc_is_circ)

    fam_texts = [t for t, c in zip(doc_texts, doc_is_circ) if c == 1]
    fam_labels = [f for f, c in zip(doc_family, doc_is_circ) if c == 1]
    doc_family_clf = Pipeline([
        ("feats", FeatureUnion([
            ("word", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=2,
                                     strip_accents="unicode", max_features=40000)),
            ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5),
                                     sublinear_tf=True, min_df=2, max_features=40000)),
        ])),
        ("clf", LogisticRegression(max_iter=2000, C=4.0, class_weight="balanced")),
    ]).fit(fam_texts, fam_labels)

    # Family centroids in a shared TF-IDF space → cosine novelty score
    centroid_vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=2,
                                   strip_accents="unicode", max_features=40000)
    M = centroid_vec.fit_transform(fam_texts)
    centroids: Dict[str, np.ndarray] = {}
    for fam in sorted(set(fam_labels)):
        idx = [i for i, f in enumerate(fam_labels) if f == fam]
        c = np.asarray(M[idx].mean(axis=0)).ravel()
        norm = np.linalg.norm(c)
        centroids[fam] = c / norm if norm else c

    # ── Persist ───────────────────────────────────────────────────────────
    bundle = {
        "version": MODEL_VERSION,
        "obligation_clf": obligation_clf,
        "severity_clf": severity_clf,
        "category_clf": category_clf,
        "deadline_clf": deadline_clf,
        "intermediary_clf": intermediary_clf,
        "intermediary_labels": intermediary_labels,
        "doc_kind_clf": doc_kind_clf,
        "doc_family_clf": doc_family_clf,
        "centroid_vectorizer": centroid_vec,
        "family_centroids": centroids,
    }
    bundle_path = model_dir / "reggraph_model.joblib"
    joblib.dump(bundle, bundle_path, compress=3)
    say(f"Saved model bundle → {bundle_path} ({bundle_path.stat().st_size / 1024:.0f} KB)")

    # ── Model card ────────────────────────────────────────────────────────
    card = {
        "version": MODEL_VERSION,
        "trained_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "algorithm": "TF-IDF (word 1-3 + char_wb 3-5) → Logistic Regression",
        "corpus": {
            "circulars_total": len(all_specs),
            "demo_circulars": len(demo_specs),
            "augmented_circulars": len(aug_specs),
            "negative_documents": len(negatives),
            "labelled_sentences": len(rows),
            "obligation_sentences": int(sum(y_obl)),
            "context_sentences": int(len(rows) - sum(y_obl)),
            "families": C.DEMO_FAMILIES,
            "template_bank_size": sum(len(v) for v in C.OBLIGATION_TEMPLATES.values()),
            "document_windows": len(doc_texts),
        },
        "label_distribution": {
            "severity": dict(Counter(r["severity"] for r in obl_rows)),
            "category": dict(Counter(r["category"] for r in obl_rows)),
            "deadline_type": dict(Counter(r["deadline_type"] for r in obl_rows)),
        },
        "evaluation": evaluation,
        "intermediary_labels": intermediary_labels,
        "caveat": (
            "Corpus is synthetic and template-generated. Scores are measured on held-out "
            "templates, but real SEBI language is more varied — treat these as an upper bound "
            "and use the LLM enrichment pass for production-grade extraction."
        ),
    }
    card_path = model_dir / "model_card.json"
    card_path.write_text(json.dumps(card, indent=2))
    say(f"Saved model card  → {card_path}")
    return card


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    train_all()
