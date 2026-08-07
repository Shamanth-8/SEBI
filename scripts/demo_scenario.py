#!/usr/bin/env python
"""
The concrete regulatory scenario, end to end.

Problem Statement 2 asks for demonstrated performance on at least one concrete
regulatory scenario. This is it:

    A stockbroker is already compliant with the SEBI circular on surveillance
    of the securities market. SEBI then issues an AMENDMENT to it. What changed,
    who is affected, what must the compliance team do, and by when?

Runs the whole pipeline twice — baseline circular, then the amendment — and
prints the diff, the downstream impact and the generated action items. Uses a
scratch graph so it never disturbs the working obligation graph.

Usage:
    python scripts/demo_scenario.py                 # local model only, no API key needed
    python scripts/demo_scenario.py --with-llm      # add the LLM enrichment + insight layer
"""
import argparse
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

CORPUS = ROOT / "data" / "corpus"
BASELINE = CORPUS / "surveillance__040.pdf"
AMENDMENT = CORPUS / "holdout" / "holdout_amendment__surveillance__204.pdf"

RULE = "=" * 84


def _text(path: Path):
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        return "".join((p.extract_text() or "") + "\n" for p in pdf.pages), len(pdf.pages)


def _banner(title: str):
    print(f"\n{RULE}\n{title}\n{RULE}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--with-llm", action="store_true",
                    help="enable LLM enrichment and the AI insight layer")
    ap.add_argument("--keep-graph", action="store_true",
                    help="write into the real obligation graph instead of a scratch copy")
    args = ap.parse_args()

    for p in (BASELINE, AMENDMENT):
        if not p.exists():
            print(f"Missing {p}. Run: python scripts/generate_corpus.py")
            return 1

    mode = "hybrid" if args.with_llm else "ml"
    os.environ["EXTRACTION_MODE"] = mode
    os.environ["ENABLE_AI_INSIGHTS"] = "true" if args.with_llm else "false"

    tmpdir = None
    if not args.keep_graph:
        tmpdir = tempfile.mkdtemp(prefix="reggraph_demo_")
        os.environ["GRAPH_DB_PATH"] = str(Path(tmpdir) / "graph.pkl")
        os.environ["FAISS_INDEX_PATH"] = str(Path(tmpdir) / "faiss_index")

    logging.basicConfig(level=logging.ERROR)
    from app.agents.orchestrator import RegGraphOrchestrator      # noqa: E402
    from app.config import get_settings                            # noqa: E402
    get_settings.cache_clear()

    intermediaries = ["stockbroker", "depository"]

    try:
        orch = RegGraphOrchestrator()

        _banner("SCENARIO — SEBI amends the surveillance circular for stockbrokers")
        print(f"  extraction mode : {mode}"
              f"{' (LLM enrichment on)' if args.with_llm else ' (offline, no API key)'}")
        print(f"  intermediaries  : {', '.join(intermediaries)}")
        print(f"  graph           : {'real' if args.keep_graph else 'scratch copy'}")

        # ── Step 1: the baseline circular the firm already complies with ──
        _banner("STEP 1 — Ingest the circular already in force")
        text, pages = _text(BASELINE)
        r1 = orch.process_circular(text, "SEBI_ISD_CIR_2026_040",
                                   "Strengthening of Surveillance Mechanism and Alert Disposal",
                                   intermediaries, pages=pages)
        rec1 = r1["recognition"]
        print(f"  {BASELINE.name}  ({pages} pages)")
        print(f"  recognised as   : {rec1.get('verdict')}")
        print(f"  obligations     : {len(r1['extracted_obligations'])}")
        print(f"  graph now holds : {r1['graph_stats'].get('total_obligations', 0)} obligations")

        # ── Step 2: SEBI issues the amendment ────────────────────────────
        _banner("STEP 2 — SEBI issues an amendment; what changed?")
        text2, pages2 = _text(AMENDMENT)
        r2 = orch.process_circular(text2, "SEBI_ISD_CIR_2026_204",
                                   "Surveillance Mechanism — Amendment",
                                   intermediaries, pages=pages2)
        diff = r2["diff_result"]
        print(f"  {AMENDMENT.name}  ({pages2} pages)")
        print(f"  recognised as   : {r2['recognition'].get('verdict')}")
        print(f"  obligations     : {len(r2['extracted_obligations'])}")
        print()
        print(f"  NEW             : {len(diff.new_obligations)}")
        print(f"  MODIFIED        : {len(diff.modified_obligations)}")
        print(f"  SUPERSEDED      : {len(diff.superseded_obligations)}")
        print(f"  impact score    : {diff.impact_score}")

        if diff.modified_obligations:
            print("\n  What actually changed:")
            for mod in diff.modified_obligations[:5]:
                obl = mod.get("new_obligation")
                print(f"    • {obl.title[:66]}")
                print(f"      vs {mod.get('old_id')} "
                      f"(similarity {mod.get('similarity', '—')}, {mod.get('method', 'llm')})")
                for ch in (mod.get("changes") or [])[:3]:
                    print(f"        - {ch}")

        if diff.new_obligations:
            print("\n  Genuinely new obligations:")
            for obl in diff.new_obligations[:5]:
                print(f"    • [{obl.severity}] {obl.title[:66]}")
                print(f"      owner: {obl.responsible_party[:44]} · "
                      f"deadline: {obl.deadline or 'not stated'}")

        # ── Step 3: downstream impact ────────────────────────────────────
        _banner("STEP 3 — Which existing obligations are affected downstream?")
        prop = r2["impact_propagation"]
        print(f"  directly affected   : {len(prop.get('directly_affected', []))}")
        print(f"  total affected      : {prop.get('total_affected_count', 0)}")
        print(f"  overall risk level  : {r2['impact_report'].risk_level}")

        # ── Step 4: operational action ───────────────────────────────────
        _banner("STEP 4 — Operational action items generated")
        actions = r2["compliance_actions"]
        print(f"  {len(actions)} tasks created across "
              f"{len({a.department for a in actions})} departments\n")
        rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        for a in sorted(actions, key=lambda x: rank.get(x.priority, 9))[:5]:
            print(f"    [{a.priority.upper():<8}] {a.title[:60]}")
            print(f"               {a.department} · owner {a.owner[:34]} · "
                  f"due {a.due_date or 'TBD'}")
            if a.steps:
                print(f"               step 1: {a.steps[0][:70]}")

        # ── Step 5: evidence position ────────────────────────────────────
        _banner("STEP 5 — Evidence position and compliance score")
        scores = r2["compliance_scores"]
        for k, v in scores.items():
            print(f"  {k:<22} {v:>6.1f}%")
        pre = r2["pre_ai_insights"]
        m = pre.get("summary_metrics", {})
        print(f"\n  obligations with no stated deadline : {m.get('without_deadline', 0)}")
        print(f"  recurring obligations               : {m.get('recurring_obligations', 0)}")
        print(f"  evidence gaps (red)                 : "
              f"{sum(1 for o in r2['extracted_obligations'] if o.evidence_status.value == 'red')}")

        print("\n  Deterministic findings:")
        for f in pre.get("findings", [])[:6]:
            print(f"    [{f['level']:<7}] {f['title']}")

        ai = r2.get("ai_insights") or {}
        if ai.get("available"):
            _banner("STEP 6 — AI insight layer (grounded on the numbers above)")
            ins = ai.get("insights", {})
            if ins.get("executive_summary"):
                print(f"  {ins['executive_summary']}\n")
            for r in (ins.get("key_risks") or [])[:3]:
                if isinstance(r, dict):
                    print(f"    RISK: {r.get('risk')}")
                    print(f"          {r.get('why')}")
            for a in (ins.get("first_30_days") or [])[:3]:
                print(f"    DO:   {a}")
        elif args.with_llm:
            _banner("STEP 6 — AI insight layer unavailable")
            print(f"  {str(ai.get('error'))[:200]}")
            print("  Everything above was still produced — that is the point of the "
                  "local-model-first design.")

        _banner("SCENARIO COMPLETE")
        print("  Regulatory text → structured obligations → classified change → "
              "downstream impact\n  → assigned tasks with SOPs → evidence gaps → audit trail.")
        return 0

    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
