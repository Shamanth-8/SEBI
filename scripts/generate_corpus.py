#!/usr/bin/env python
"""
Generate the synthetic SEBI circular corpus.

Writes:
  data/corpus/*.pdf                 5 demo circulars (one per family)
  data/corpus/holdout/*.pdf         2 unseen circulars for testing recognition
  data/corpus/negative/*.pdf        non-circular documents (should be rejected)
  data/corpus/ground_truth.json     every clause with its true labels

Usage:  python scripts/generate_corpus.py
"""
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.ml import corpus as C                      # noqa: E402
from app.ml.pdf_render import render_circular_pdf, render_plain_pdf   # noqa: E402

OUT = ROOT / "data" / "corpus"


def _slug(spec: C.CircularSpec) -> str:
    return f"{spec.family}__{spec.reference.split('/')[-1]}"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "holdout").mkdir(exist_ok=True)
    (OUT / "negative").mkdir(exist_ok=True)

    ground_truth = {"demo": [], "holdout": []}

    print("Generating demo circulars …")
    for spec in C.build_demo_corpus():
        path = OUT / f"{_slug(spec)}.pdf"
        render_circular_pdf(spec, path)
        n_obl = sum(1 for c in spec.all_clauses if c.is_obligation)
        print(f"  ✓ {path.name:52} {n_obl:>3} obligations  ({path.stat().st_size // 1024} KB)")
        ground_truth["demo"].append(_gt(spec))
        (OUT / f"{_slug(spec)}.txt").write_text(spec.to_text())

    print("\nGenerating holdout circulars (unseen at training time) …")
    for label, spec in C.build_holdout_specs():
        path = OUT / "holdout" / f"{label}__{_slug(spec)}.pdf"
        render_circular_pdf(spec, path)
        n_obl = sum(1 for c in spec.all_clauses if c.is_obligation)
        print(f"  ✓ {path.name:52} {n_obl:>3} obligations")
        gt = _gt(spec)
        gt["holdout_kind"] = label
        ground_truth["holdout"].append(gt)
        (OUT / "holdout" / f"{label}.txt").write_text(spec.to_text())

    print("\nGenerating negative (non-circular) documents …")
    for name, text in C.build_negative_documents(n=4):
        path = OUT / "negative" / f"{name}.pdf"
        render_plain_pdf(name, text, path)
        print(f"  ✓ {path.name}")

    gt_path = OUT / "ground_truth.json"
    gt_path.write_text(json.dumps(ground_truth, indent=2, default=str))
    print(f"\nGround truth → {gt_path}")
    print(f"Corpus ready in {OUT}")
    return 0


def _gt(spec: C.CircularSpec) -> dict:
    return {
        "circular_id": spec.circular_id,
        "reference": spec.reference,
        "family": spec.family,
        "subject": spec.subject,
        "issue_date": str(spec.issue_date),
        "effective_date": str(spec.effective_date),
        "intermediary_types": spec.intermediary_types,
        "clauses": [asdict(c) for c in spec.all_clauses],
    }


if __name__ == "__main__":
    raise SystemExit(main())
