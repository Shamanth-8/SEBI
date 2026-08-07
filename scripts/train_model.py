#!/usr/bin/env python
"""
Train the local RegGraph classifier bundle on the synthetic corpus.

Usage:
    python scripts/train_model.py                 # default (6 augmented docs / family)
    python scripts/train_model.py --n-per-family 10
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.ml.train import train_all   # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-per-family", type=int, default=6,
                    help="augmented circulars generated per family for training")
    ap.add_argument("--seed", type=int, default=4242)
    ap.add_argument("--model-dir", default=str(ROOT / "data" / "models"))
    args = ap.parse_args()

    card = train_all(model_dir=Path(args.model_dir),
                     n_per_family=args.n_per_family, seed=args.seed)

    print("\n── Model card ───────────────────────────────────────────────")
    ev = card["evaluation"]
    print(f"  protocol : {ev['protocol']}")
    for head in ("obligation_clf", "severity_clf", "category_clf", "deadline_clf"):
        if ev.get(head):
            print(f"  {head:16}: {ev[head]}")
    print(f"  corpus   : {card['corpus']['circulars_total']} circulars, "
          f"{card['corpus']['labelled_sentences']} labelled sentences")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
