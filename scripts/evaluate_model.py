#!/usr/bin/env python
"""
Evaluate the trained model against the corpus ground truth and the holdout PDFs.

Unlike the numbers in the model card (which are measured on sentences), this runs
the *whole* path a real upload takes — PDF → pdfplumber → segmentation →
classification → obligations — and scores the result against the clauses that
were actually written into each document.

Usage:  python scripts/evaluate_model.py
"""
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

import pdfplumber                                    # noqa: E402
from app.ml.extractor import extract_obligations_ml  # noqa: E402
from app.ml.model import RegGraphModel               # noqa: E402

CORPUS = ROOT / "data" / "corpus"


def _norm(s: str) -> Set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", s.lower())}


def _overlap(a: str, b: str) -> float:
    """Jaccard-ish containment: how much of the shorter text the longer one covers."""
    ta, tb = _norm(a), _norm(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def pdf_text(path: Path) -> Tuple[str, int]:
    with pdfplumber.open(path) as pdf:
        return "".join((p.extract_text() or "") + "\n" for p in pdf.pages), len(pdf.pages)


def score_document(text: str, truth_clauses: List[Dict], threshold: float,
                   match_at: float = 0.6) -> Dict:
    """Precision / recall of extracted obligations against the true clauses."""
    obligations, diag = extract_obligations_ml(text, "EVAL", "Evaluation", threshold=threshold)
    true_obl = [c for c in truth_clauses if c["is_obligation"]]

    matched_truth: Set[int] = set()
    true_positives = 0
    for o in obligations:
        best_i, best = -1, 0.0
        for i, c in enumerate(true_obl):
            s = _overlap(o.description, c["text"])
            if s > best:
                best, best_i = s, i
        if best >= match_at:
            true_positives += 1
            matched_truth.add(best_i)

    precision = true_positives / len(obligations) if obligations else 0.0
    recall = len(matched_truth) / len(true_obl) if true_obl else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    # Severity agreement on the obligations we did match
    sev_hits = sev_total = 0
    for o in obligations:
        for c in true_obl:
            if _overlap(o.description, c["text"]) >= match_at:
                sev_total += 1
                sev_hits += int(o.severity == c["severity"])
                break

    return {
        "extracted": len(obligations),
        "true_obligations": len(true_obl),
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "severity_accuracy": round(sev_hits / sev_total, 3) if sev_total else 0.0,
        "mean_confidence": diag.get("mean_confidence", 0.0),
    }


def main() -> int:
    if not RegGraphModel.available():
        print("No trained model. Run: python scripts/train_model.py")
        return 1
    gt_path = CORPUS / "ground_truth.json"
    if not gt_path.exists():
        print("No corpus. Run: python scripts/generate_corpus.py")
        return 1

    model = RegGraphModel.get()
    gt = json.loads(gt_path.read_text())
    threshold = 0.55

    print("=" * 88)
    print("RECOGNITION — is it a circular, and which family?")
    print("=" * 88)
    print(f"{'document':<48}{'circ':>6}{'family':>22}{'conf':>7}{'novel':>7}")

    groups = [
        ("demo", sorted(CORPUS.glob("*.pdf"))),
        ("holdout", sorted((CORPUS / "holdout").glob("*.pdf"))),
        ("negative", sorted((CORPUS / "negative").glob("*.pdf"))),
    ]
    real = ROOT / "circular.pdf"
    if real.exists():
        groups.append(("real SEBI circular", [real]))

    for label, paths in groups:
        if not paths:
            continue
        print(f"\n[{label}]")
        for p in paths:
            text, _ = pdf_text(p)
            r = model.recognize_document(text)
            print(f"  {p.name[:46]:<46}{r['circular_confidence']:>6.2f}"
                  f"{str(r['family'])[:20]:>22}{r['family_confidence']:>7.2f}"
                  f"{'yes' if r['is_novel_topic'] else 'no':>7}")

    print()
    print("=" * 88)
    print(f"EXTRACTION — obligations recovered from the PDF (threshold {threshold})")
    print("=" * 88)
    print(f"{'document':<44}{'found':>7}{'true':>6}{'prec':>7}{'rec':>7}{'F1':>7}{'sev acc':>9}")

    def run_group(entries: List[Dict], finder):
        agg = {"precision": [], "recall": [], "f1": [], "severity_accuracy": []}
        for entry in entries:
            path = finder(entry)
            if path is None:
                continue
            text, _ = pdf_text(path)
            s = score_document(text, entry["clauses"], threshold)
            print(f"  {path.name[:42]:<42}{s['extracted']:>7}{s['true_obligations']:>6}"
                  f"{s['precision']:>7.2f}{s['recall']:>7.2f}{s['f1']:>7.2f}"
                  f"{s['severity_accuracy']:>9.2f}")
            for k in agg:
                agg[k].append(s[k])
        if agg["f1"]:
            print(f"  {'MEAN':<42}{'':>7}{'':>6}"
                  f"{sum(agg['precision'])/len(agg['precision']):>7.2f}"
                  f"{sum(agg['recall'])/len(agg['recall']):>7.2f}"
                  f"{sum(agg['f1'])/len(agg['f1']):>7.2f}"
                  f"{sum(agg['severity_accuracy'])/len(agg['severity_accuracy']):>9.2f}")

    print("\n[demo circulars — the model was trained on these]")
    run_group(gt["demo"], lambda e: next(
        (p for p in CORPUS.glob("*.pdf") if e["reference"].split("/")[-1] in p.name), None))

    print("\n[holdout circulars — never seen during training]")
    run_group(gt["holdout"], lambda e: next(
        ((CORPUS / "holdout").glob(f"*{e['reference'].split('/')[-1]}*").__iter__().__next__()
         for _ in [0]), None))

    if real.exists():
        text, pages = pdf_text(real)
        obls, diag = extract_obligations_ml(text, "REAL", "Real SEBI circular",
                                            threshold=threshold)
        print(f"\n[real SEBI circular — no ground truth, reported for scale]")
        print(f"  circular.pdf: {pages} pages, {diag['sentences_considered']} candidate "
              f"sentences → {len(obls)} obligations "
              f"(mean confidence {diag['mean_confidence']})")

    print("\nNote: demo-circular scores are optimistic — those documents are in the training")
    print("set. The holdout row is the number that predicts behaviour on a new circular.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
