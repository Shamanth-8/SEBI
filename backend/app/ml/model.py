"""
Inference wrapper around the trained RegGraph model bundle.

Loaded once per process and reused. Everything here is CPU-only and takes
milliseconds, which is why it can run *before* any LLM call and still feel instant.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from app.ml.textutil import is_boilerplate, split_sentences, strip_clause_number

logger = logging.getLogger(__name__)

def _model_dir() -> Path:
    """
    Where the trained artefacts live.

    Read from settings (MODEL_DIR) rather than hardcoded, so a container can keep
    the model inside the image while a persistent volume is mounted over ./data —
    otherwise the mount hides the model and the offline path silently dies.
    """
    try:
        from app.config import get_settings
        return Path(get_settings().MODEL_DIR)
    except Exception:
        return Path("data/models")


DEFAULT_MODEL_PATH = _model_dir() / "reggraph_model.joblib"
DEFAULT_CARD_PATH = _model_dir() / "model_card.json"

# Thresholds calibrated on the corpus: documents from a trained family score
# centroid similarity 0.82-0.88 and family confidence 0.86-0.95, while circulars
# on unseen subject matter (the outsourcing holdout, the real 38-page master
# circular) score 0.33-0.41 and 0.23-0.26. Anything in the gap is reported as a
# topic outside the trained families rather than labelled with a family it only
# marginally resembles.
NOVELTY_SIMILARITY_THRESHOLD = 0.60
FAMILY_CONFIDENCE_THRESHOLD = 0.55


class ModelNotTrained(RuntimeError):
    """Raised when inference is attempted before `python -m scripts.train_model`."""


def _version_mismatch_message(path: Path, exc: Exception) -> str:
    """Explain a failed model load in terms of the thing that actually went wrong."""
    import sys

    try:
        import sklearn
        running = sklearn.__version__
        location = sklearn.__file__
    except Exception:
        running = "not installed"
        location = "n/a"

    return (
        f"Could not load the model at {path}: {type(exc).__name__}: {exc}\n\n"
        f"This is almost always a scikit-learn version mismatch — the model is being\n"
        f"loaded by a different Python than the one that trained it.\n\n"
        f"  interpreter : {sys.executable}\n"
        f"  scikit-learn: {running}  ({location})\n\n"
        f"Fix: run everything with the project venv, not bare `python`:\n"
        f"  ./venv/bin/python scripts/evaluate_model.py\n"
        f"  PYTHONPATH=backend ./venv/bin/python -m uvicorn app.main:app --port 8000\n"
        f"  ./venv/bin/streamlit run frontend/dashboard.py\n\n"
        f"Or retrain against the interpreter you are using:\n"
        f"  python scripts/train_model.py"
    )


class RegGraphModel:
    """Loads the joblib bundle and exposes prediction helpers."""

    _instance: Optional["RegGraphModel"] = None
    _lock = threading.Lock()

    def __init__(self, bundle: Dict, card: Optional[Dict] = None):
        self.bundle = bundle
        self.card = card or {}
        self.version = bundle.get("version", "unknown")
        self._feature_cache: Dict[int, Tuple[np.ndarray, np.ndarray]] = {}

    # ── Loading ───────────────────────────────────────────────────────────

    @classmethod
    def load(cls, path: Path | str = DEFAULT_MODEL_PATH,
             card_path: Path | str = DEFAULT_CARD_PATH) -> "RegGraphModel":
        import joblib, json

        path = Path(path)
        if not path.exists():
            raise ModelNotTrained(
                f"No trained model at {path}. Run: python scripts/train_model.py"
            )
        try:
            bundle = joblib.load(path)
        except Exception as exc:
            # A scikit-learn version mismatch surfaces as an obscure AttributeError
            # deep inside the estimator (e.g. "no attribute 'multi_class'"), which
            # sends people hunting for a bug in this code. Name the real cause.
            raise ModelNotTrained(_version_mismatch_message(path, exc)) from exc
        card = {}
        card_path = Path(card_path)
        if card_path.exists():
            try:
                card = json.loads(card_path.read_text())
            except Exception:
                pass

        # joblib.load() only warns on a version mismatch; the failure lands later,
        # mid-request, as an AttributeError inside sklearn. One throwaway prediction
        # here turns that into an actionable message at startup instead.
        try:
            bundle["obligation_clf"].predict_proba(["The broker shall submit a report."])
        except Exception as exc:
            raise ModelNotTrained(_version_mismatch_message(path, exc)) from exc

        logger.info(f"Loaded RegGraph model v{bundle.get('version')} from {path}")
        return cls(bundle, card)

    @classmethod
    def get(cls) -> "RegGraphModel":
        """Process-wide singleton; safe to call from FastAPI request handlers."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls.load()
        return cls._instance

    @classmethod
    def available(cls) -> bool:
        return Path(DEFAULT_MODEL_PATH).exists()

    @classmethod
    def reset(cls) -> None:
        """Drop the cached singleton (used after retraining)."""
        with cls._lock:
            cls._instance = None

    # ── Document-level recognition ────────────────────────────────────────

    def _windows(self, text: str, window: int = 1200) -> List[str]:
        flat = " ".join(text.split())
        if len(flat) <= window:
            return [flat] if flat else []
        step = window // 2
        out = [flat[i:i + window] for i in range(0, len(flat) - step, step)]
        return [w for w in out if len(w) >= 250] or [flat[:window]]

    def recognize_document(self, text: str) -> Dict:
        """
        Answer three questions about an uploaded file, before any LLM is involved:
          1. Is this a SEBI-style regulatory circular at all?
          2. Which known circular family does it resemble?
          3. Is its subject matter something the model has actually seen?
        """
        windows = self._windows(text)
        if not windows:
            return {
                "is_circular": False, "circular_confidence": 0.0,
                "family": None, "family_confidence": 0.0,
                "family_scores": {}, "novelty": 1.0, "is_novel_topic": True,
                "verdict": "empty document", "windows_analysed": 0,
            }

        kind = self.bundle["doc_kind_clf"]
        kind_proba = kind.predict_proba(windows)
        circ_idx = list(kind.classes_).index(1)
        circ_conf = float(kind_proba[:, circ_idx].mean())

        fam_clf = self.bundle["doc_family_clf"]
        fam_proba = fam_clf.predict_proba(windows).mean(axis=0)
        fam_scores = {c: round(float(p), 4) for c, p in zip(fam_clf.classes_, fam_proba)}
        best_i = int(np.argmax(fam_proba))
        family = str(fam_clf.classes_[best_i])
        family_conf = float(fam_proba[best_i])

        # Cosine similarity to each family centroid — an absolute measure that,
        # unlike softmax probabilities, can say "none of the above".
        vec = self.bundle["centroid_vectorizer"]
        v = np.asarray(vec.transform([" ".join(windows)]).todense()).ravel()
        n = np.linalg.norm(v)
        v = v / n if n else v
        sims = {fam: float(np.dot(v, c)) for fam, c in self.bundle["family_centroids"].items()}
        best_sim = max(sims.values()) if sims else 0.0
        # Two independent signals must agree before a family label is asserted:
        # the softmax winner (which is always *some* family) and an absolute
        # similarity that can say "none of the above".
        is_novel = (best_sim < NOVELTY_SIMILARITY_THRESHOLD
                    or family_conf < FAMILY_CONFIDENCE_THRESHOLD)

        is_circ = circ_conf >= 0.5
        if not is_circ:
            verdict = "Not recognised as a regulatory circular"
        elif is_novel:
            verdict = ("Recognised as a SEBI circular, but on a topic outside the "
                       f"trained families (closest: {family.replace('_', ' ')})")
        else:
            verdict = f"Recognised as a SEBI circular — {family.replace('_', ' ')}"

        return {
            "is_circular": is_circ,
            "circular_confidence": round(circ_conf, 4),
            "family": family if is_circ else None,
            "family_confidence": round(family_conf, 4),
            "family_scores": fam_scores,
            "centroid_similarity": {k: round(v_, 4) for k, v_ in sorted(
                sims.items(), key=lambda kv: -kv[1])},
            "novelty": round(1.0 - best_sim, 4),
            "is_novel_topic": bool(is_novel),
            "verdict": verdict,
            "windows_analysed": len(windows),
        }

    # ── Sentence-level classification ─────────────────────────────────────

    def candidate_sentences(self, text: str) -> List[str]:
        """Sentences worth scoring — boilerplate is dropped up front."""
        return [s for s in split_sentences(text) if not is_boilerplate(s)]

    def classify_sentences(self, sentences: Sequence[str],
                           threshold: float = 0.5) -> List[Dict]:
        """Score every sentence; obligations additionally get the detail heads."""
        if not sentences:
            return []
        sentences = list(sentences)

        obl_clf = self.bundle["obligation_clf"]
        proba = obl_clf.predict_proba(sentences)
        pos_idx = list(obl_clf.classes_).index(1)
        scores = proba[:, pos_idx]

        results = [
            {"text": s, "obligation_probability": round(float(p), 4),
             "is_obligation": bool(p >= threshold)}
            for s, p in zip(sentences, scores)
        ]

        hits = [i for i, r in enumerate(results) if r["is_obligation"]]
        if not hits:
            return results

        hit_texts = [sentences[i] for i in hits]

        def _pred(name: str) -> List[Tuple[str, float]]:
            clf = self.bundle[name]
            pr = clf.predict_proba(hit_texts)
            best = pr.argmax(axis=1)
            return [(str(clf.classes_[b]), float(pr[k, b])) for k, b in enumerate(best)]

        severity = _pred("severity_clf")
        category = _pred("category_clf")
        deadline = _pred("deadline_clf")

        inter_clf = self.bundle["intermediary_clf"]
        inter_labels = self.bundle["intermediary_labels"]
        inter_proba = inter_clf.predict_proba(hit_texts)

        for k, i in enumerate(hits):
            r = results[i]
            r["severity"], r["severity_confidence"] = severity[k][0], round(severity[k][1], 4)
            r["category"], r["category_confidence"] = category[k][0], round(category[k][1], 4)
            r["deadline_type"], r["deadline_confidence"] = deadline[k][0], round(deadline[k][1], 4)
            row = inter_proba[k]
            picked = [lbl for lbl, p in zip(inter_labels, row) if p >= 0.5]
            if not picked and len(row):
                picked = [inter_labels[int(np.argmax(row))]]
            r["intermediary_types"] = picked
            r["intermediary_scores"] = {
                lbl: round(float(p), 3) for lbl, p in zip(inter_labels, row)
            }
        return results

    # ── Explainability ────────────────────────────────────────────────────

    def explain(self, sentence: str, model_name: str = "obligation_clf",
                top_k: int = 6) -> List[Dict]:
        """
        Return the n-grams that pushed the prediction, with signed contributions.

        contribution = tfidf_value * logistic_regression_coefficient, i.e. the
        exact additive terms of the decision function — not a post-hoc guess.
        """
        pipe = self.bundle[model_name]
        feats = pipe.named_steps["feats"]
        clf = pipe.named_steps["clf"]

        names = self._feature_names(model_name, feats)
        coef = clf.coef_
        if coef.shape[0] == 1:
            w = coef[0]
        else:
            probs = pipe.predict_proba([sentence])[0]
            w = coef[int(np.argmax(probs))]

        x = feats.transform([sentence])
        x = x.tocoo()
        contribs = [(names[j], float(v * w[j])) for j, v in zip(x.col, x.data)]
        contribs.sort(key=lambda kv: -abs(kv[1]))

        out = []
        for name, c in contribs[:top_k * 3]:
            # Character n-grams are noisy to read; prefer whole-word evidence.
            if name.startswith("char__") and len(out) >= top_k // 2:
                continue
            out.append({
                "feature": name.split("__", 1)[-1].strip(),
                "contribution": round(c, 4),
                "direction": "supports" if c > 0 else "opposes",
            })
            if len(out) >= top_k:
                break
        return out

    def _feature_names(self, key: str, feats) -> List[str]:
        cached = getattr(self, "_names_cache", None)
        if cached is None:
            cached = {}
            self._names_cache = cached
        if key not in cached:
            cached[key] = list(feats.get_feature_names_out())
        return cached[key]

    # ── Metadata ──────────────────────────────────────────────────────────

    def info(self) -> Dict:
        return {
            "version": self.version,
            "model_path": str(DEFAULT_MODEL_PATH),
            "heads": [
                "obligation_clf", "severity_clf", "category_clf",
                "deadline_clf", "intermediary_clf", "doc_kind_clf", "doc_family_clf",
            ],
            "card": self.card,
        }
