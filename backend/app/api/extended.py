"""
Extended API endpoints for RegGraph — Tiers 1-4 features.
Mounted under /api/v1/
"""
import json
import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ─── shared orchestrator ref ─────────────────────────────────────────────────
from app.api.circulars import orchestrator

router = APIRouter()


# ══════════════════════════════════════════════════════════════════════════════
# Tier 1A — Compliance Actions
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/actions")
async def list_compliance_actions(
    intermediary_type: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """
    Return generated compliance action tasks.
    Sorted by priority + urgency.
    """
    actions = orchestrator.get_compliance_actions(intermediary_type)
    if priority:
        actions = [a for a in actions if a.priority == priority]
    actions = actions[:limit]
    return {
        "total": len(actions),
        "actions": [a.model_dump() for a in actions],
    }


@router.get("/actions/{obligation_id}")
async def get_actions_for_obligation(obligation_id: str):
    """Get compliance action(s) for a specific obligation."""
    actions = [
        a for a in orchestrator.get_compliance_actions()
        if a.obligation_id == obligation_id
    ]
    return {"obligation_id": obligation_id, "actions": [a.model_dump() for a in actions]}


# ══════════════════════════════════════════════════════════════════════════════
# Tier 1B — Risk Score
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/risk/{obligation_id}")
async def get_obligation_risk(obligation_id: str):
    """Get the computed risk score for a single obligation."""
    obl = orchestrator.graph.get_obligation(obligation_id)
    if not obl:
        raise HTTPException(404, f"Obligation {obligation_id} not found")

    from app.agents.risk_calculator import compute_risk_score
    dep_count = len(list(orchestrator.graph.graph.successors(obligation_id)))
    score, label = compute_risk_score(obl, dep_count)

    return {
        "obligation_id": obligation_id,
        "title": obl.title,
        "risk_score": score,
        "risk_label": label,
        "severity": obl.severity,
        "evidence_status": obl.evidence_status.value,
        "dep_count": dep_count,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Tier 1C — Manual vs AI Benchmark
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/audit/benchmark")
async def get_benchmark():
    """
    Manual-vs-AI time comparison table.
    Manual times are assumed industry estimates.
    RegGraph times are pulled from the latest metrics record.
    """
    from app.metrics import get_latest_run

    latest = get_latest_run()

    # Measured pipeline timings (seconds)
    extraction_s = latest["extraction"]["seconds"] if latest else 40
    diff_s = latest["diff"]["seconds"] if latest else 20
    mapping_s = latest["mapping"]["seconds"] if latest else 60
    total_s = latest["overall"]["total_seconds"] if latest else 180

    manual_read_s = 3 * 3600          # 3 hours
    manual_extract_s = 2 * 3600       # 2 hours
    manual_diff_s = 4 * 3600          # 4 hours
    manual_map_s = 5 * 3600           # 5 hours
    manual_audit_s = 3 * 3600         # 3 hours
    manual_total_s = manual_read_s + manual_extract_s + manual_diff_s + manual_map_s + manual_audit_s

    def fmt(seconds: float) -> str:
        if seconds < 60:
            return f"{seconds:.0f} sec"
        if seconds < 3600:
            return f"{seconds/60:.0f} min"
        return f"{seconds/3600:.1f} hrs"

    speedup = round(manual_total_s / max(total_s, 1), 1)
    pct_faster = round((1 - total_s / manual_total_s) * 100, 1)

    rows = [
        {
            "task": "Read & understand circular",
            "manual": fmt(manual_read_s),
            "regraph": "2 min",
            "manual_seconds": manual_read_s,
            "regraph_seconds": 120,
        },
        {
            "task": "Extract obligations",
            "manual": fmt(manual_extract_s),
            "regraph": fmt(extraction_s),
            "manual_seconds": manual_extract_s,
            "regraph_seconds": extraction_s,
        },
        {
            "task": "Identify changes (diff)",
            "manual": fmt(manual_diff_s),
            "regraph": fmt(diff_s),
            "manual_seconds": manual_diff_s,
            "regraph_seconds": diff_s,
        },
        {
            "task": "Map obligations to intermediaries",
            "manual": fmt(manual_map_s),
            "regraph": fmt(mapping_s),
            "manual_seconds": manual_map_s,
            "regraph_seconds": mapping_s,
        },
        {
            "task": "Generate audit trail",
            "manual": fmt(manual_audit_s),
            "regraph": "Instant",
            "manual_seconds": manual_audit_s,
            "regraph_seconds": 0,
        },
        {
            "task": "TOTAL",
            "manual": fmt(manual_total_s),
            "regraph": fmt(total_s),
            "manual_seconds": manual_total_s,
            "regraph_seconds": total_s,
        },
    ]

    return {
        "benchmark_rows": rows,
        "headline": f"{speedup}× faster",
        "pct_faster": pct_faster,
        "manual_total_hours": round(manual_total_s / 3600, 1),
        "regraph_total_minutes": round(total_s / 60, 1),
        "tagline": f"~17 hours → ~{round(total_s/60)} minutes ({pct_faster}% faster)",
        "note": "Manual times are industry estimates for a trained compliance analyst.",
    }


# ══════════════════════════════════════════════════════════════════════════════
# Tier 2A — Deadline urgency queue (canonical route in obligations.py)
# ══════════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════════
# Tier 2B — Compliance Score
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/compliance/score")
async def get_overall_compliance_score():
    """Overall compliance score + per-intermediary breakdown."""
    all_obls = orchestrator.graph.get_all_obligations()
    intermediary_types = list(set(
        itype for o in all_obls for itype in o.intermediary_types
    ))
    scores = orchestrator.get_compliance_scores(intermediary_types)
    return {"scores": scores, "intermediary_breakdown": scores}


@router.get("/compliance/score/{intermediary_type}")
async def get_intermediary_compliance_score(intermediary_type: str):
    """Compliance score for a specific intermediary type."""
    scores = orchestrator.get_compliance_scores([intermediary_type])
    return {
        "intermediary_type": intermediary_type,
        "compliance_score": scores.get(intermediary_type, 100.0),
        "scores": scores,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Tier 2C — SOP Generator  (canonical route lives in obligations.py)
# Tier 3B — Timeline        (canonical route lives in obligations.py)
# Tier 3C — Explainability  (canonical route lives in obligations.py)
# Tier 3D — Evidence Checklist (canonical routes live in evidence.py)
# All duplicates removed — routes registered once in their natural routers.
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/circulars/{circular_id}/impact-summary")
async def get_impact_summary(circular_id: str):
    """
    Post-pipeline summary card for a circular.
    Aggregates diff, tasks, scores — shows the business impact at a glance.
    """
    summary = orchestrator.get_copilot_summary()
    if not summary or summary.get("circular_id") != circular_id:
        # Build a lighter version from stored data
        obligations = orchestrator.graph.get_by_circular(circular_id)
        if not obligations:
            raise HTTPException(404, f"Circular {circular_id} not found or not processed")

        actions = orchestrator.get_compliance_actions()
        circ_actions = [a for a in actions if a.circular_id == circular_id]
        all_itypes = list(set(i for o in obligations for i in o.intermediary_types))
        scores = orchestrator.get_compliance_scores(all_itypes)

        from app.agents.action_agent import _compute_days_remaining
        from app.agents.risk_calculator import compute_risk_score

        high_risk = []
        for o in obligations:
            dep_count = len(list(orchestrator.graph.graph.successors(o.obligation_id)))
            score, label = compute_risk_score(o, dep_count)
            if label == "High":
                high_risk.append({"id": o.obligation_id, "title": o.title, "risk_score": score})

        return {
            "circular_id": circular_id,
            "total_obligations": len(obligations),
            "affected_intermediaries": all_itypes,
            "tasks_created": len(circ_actions),
            "high_risk_obligations": high_risk[:5],
            "compliance_scores": scores,
            "evidence_gaps": sum(1 for o in obligations if o.evidence_status.value == "red"),
        }

    return summary


# ══════════════════════════════════════════════════════════════════════════════
# Tier 2E — Exportable HTML Compliance Report
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/compliance/report/{intermediary_type}")
async def get_compliance_report_html(intermediary_type: str):
    """
    Generate a downloadable HTML compliance report for an intermediary.
    Returns HTML string (save as .html to open offline).
    """
    from fastapi.responses import HTMLResponse
    from app.agents.mapping_agent import ComplianceMappingAgent
    from app.agents.risk_calculator import compute_risk_score
    from app.agents.action_agent import _compute_days_remaining

    mapper = ComplianceMappingAgent(orchestrator.graph)
    mapped = mapper.map_obligations_to_intermediary(intermediary_type)
    scores = orchestrator.get_compliance_scores([intermediary_type])
    score_val = scores.get(intermediary_type, 0.0)

    rows = ""
    for obl in sorted(mapped.applicable_obligations, key=lambda o: o.severity != "high"):
        dep_count = len(list(orchestrator.graph.graph.successors(obl.obligation_id)))
        risk_score, risk_label = compute_risk_score(obl, dep_count)
        ev_color = {"green": "#22c55e", "yellow": "#f59e0b", "red": "#ef4444"}
        sev_color = {"high": "#ef4444", "medium": "#f59e0b", "low": "#22c55e"}
        rows += f"""<tr>
          <td>{obl.obligation_id}</td>
          <td>{obl.title}</td>
          <td>{obl.clause_reference}</td>
          <td style="color:{sev_color.get(obl.severity,'#888')}">{obl.severity.upper()}</td>
          <td>{obl.deadline or '—'}</td>
          <td style="color:{ev_color.get(obl.evidence_status.value,'#888')}">{obl.evidence_status.value.upper()}</td>
          <td><b>{risk_score:.0f}</b> ({risk_label})</td>
          <td>{obl.responsible_party}</td>
        </tr>"""

    from app.audit import get_summary as audit_summary
    audit = audit_summary()

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>RegGraph Compliance Report — {intermediary_type.replace('_',' ').title()}</title>
<style>
  body {{ font-family: Inter, system-ui, sans-serif; background: #0B0F19; color: #E2E8F0; padding: 40px; }}
  h1 {{ color: #A78BFA; }} h2 {{ color: #94A3B8; border-bottom: 1px solid #1E293B; padding-bottom:8px; }}
  .kpi-row {{ display:flex; gap:24px; margin:24px 0; }}
  .kpi {{ background:#131826; border:1px solid #1E293B; border-radius:8px; padding:20px 28px; min-width:140px; }}
  .kpi-val {{ font-size:2rem; font-weight:700; color:#A78BFA; }}
  .kpi-lbl {{ font-size:0.8rem; color:#64748B; margin-top:4px; }}
  table {{ width:100%; border-collapse:collapse; margin-top:16px; font-size:0.85rem; }}
  th {{ background:#131826; padding:10px; text-align:left; color:#94A3B8; border-bottom:2px solid #1E293B; }}
  td {{ padding:10px; border-bottom:1px solid #1E293B; vertical-align:top; }}
  tr:hover {{ background:#131826; }}
  .footer {{ margin-top:40px; color:#475569; font-size:0.75rem; }}
</style>
</head>
<body>
<h1>🏛 RegGraph — Compliance Report</h1>
<p><b>Intermediary:</b> {intermediary_type.replace('_',' ').title()} &nbsp;|&nbsp;
   <b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')} &nbsp;|&nbsp;
   <b>System:</b> RegGraph v1.0</p>

<div class="kpi-row">
  <div class="kpi"><div class="kpi-val">{score_val:.0f}%</div><div class="kpi-lbl">Compliance Score</div></div>
  <div class="kpi"><div class="kpi-val">{len(mapped.applicable_obligations)}</div><div class="kpi-lbl">Total Obligations</div></div>
  <div class="kpi"><div class="kpi-val">{len(mapped.critical_gaps)}</div><div class="kpi-lbl">Critical Gaps</div></div>
  <div class="kpi"><div class="kpi-val">{audit.get('circulars_processed',0)}</div><div class="kpi-lbl">Circulars Processed</div></div>
</div>

<h2>Applicable Obligations</h2>
<table>
  <thead><tr><th>ID</th><th>Title</th><th>Clause</th><th>Severity</th><th>Deadline</th><th>Evidence</th><th>Risk Score</th><th>Owner</th></tr></thead>
  <tbody>{rows}</tbody>
</table>

<h2>Audit Trail Summary</h2>
<p>Total audit events: <b>{audit.get('total_events',0)}</b> &nbsp;|&nbsp;
   Circulars processed: <b>{audit.get('circulars_processed',0)}</b> &nbsp;|&nbsp;
   Last event: <b>{audit.get('last_event','—')}</b></p>

<div class="footer">
  Generated by RegGraph — Agentic Compliance System for SEBI Regulations.<br>
  This report is machine-generated for internal compliance reference only.
</div>
</body>
</html>"""

    return HTMLResponse(content=html, media_type="text/html",
                        headers={"Content-Disposition": f"attachment; filename=compliance_report_{intermediary_type}.html"})


# ══════════════════════════════════════════════════════════════════════════════
# Tier 3A — Graph Analytics
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/graph/analytics")
async def get_graph_analytics():
    """
    Expose real NetworkX analytics:
    centrality, most connected node, critical path depth, etc.
    """
    import networkx as nx
    G = orchestrator.graph.graph

    if G.number_of_nodes() == 0:
        return {"error": "No obligations in graph yet"}

    # Degree centrality
    in_degree = dict(G.in_degree())
    out_degree = dict(G.out_degree())

    # Most depended-upon (highest in-degree = others depend on it)
    most_depended = sorted(in_degree.items(), key=lambda x: -x[1])[:5]
    # Most downstream impact (highest out-degree / transitive)
    most_impactful = sorted(out_degree.items(), key=lambda x: -x[1])[:5]

    # Longest path (critical path depth)
    longest_path = 0
    try:
        longest_path = nx.dag_longest_path_length(G)
    except Exception:
        pass

    # Betweenness centrality (which nodes sit on most paths)
    betweenness = {}
    try:
        betweenness = nx.betweenness_centrality(G)
    except Exception:
        pass
    top_betweenness = sorted(betweenness.items(), key=lambda x: -x[1])[:5]

    def obl_info(obl_id: str):
        obl = orchestrator.graph.get_obligation(obl_id)
        return {
            "id": obl_id,
            "title": obl.title if obl else obl_id,
            "severity": obl.severity if obl else "—",
        }

    return {
        "total_nodes": G.number_of_nodes(),
        "total_edges": G.number_of_edges(),
        "longest_dependency_chain": longest_path,
        "most_depended_upon": [{"obligation": obl_info(k), "in_degree": v} for k, v in most_depended],
        "most_downstream_impact": [{"obligation": obl_info(k), "out_degree": v} for k, v in most_impactful],
        "top_betweenness_centrality": [{"obligation": obl_info(k), "score": round(v, 4)} for k, v in top_betweenness],
        "avg_degree": round(sum(dict(G.degree()).values()) / max(G.number_of_nodes(), 1), 2),
        "is_dag": nx.is_directed_acyclic_graph(G) if G.number_of_nodes() > 0 else True,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Tier 3B / 3C / 3D — Timeline, Explainability, Checklist
# Canonical routes registered in obligations.py and evidence.py respectively.
# ══════════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════════
# Tier 4 — Copilot Summary
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/copilot/summary")
async def get_copilot_summary():
    """Return the last Compliance Copilot summary generated by the pipeline."""
    summary = orchestrator.get_copilot_summary()
    if not summary:
        return {"message": "No circular processed yet. Run the pipeline first."}
    return summary


@router.get("/copilot/pre-ai")
async def get_pre_ai_insights():
    """Local (pre-LLM) analysis from the last pipeline run."""
    data = orchestrator.get_pre_ai_insights()
    if not data:
        return {"message": "No circular processed yet. Run the pipeline first."}
    return data


@router.get("/copilot/ai-insights")
async def get_ai_insights():
    """LLM insight layer from the last pipeline run, grounded on the local analysis."""
    data = orchestrator.get_ai_insights()
    if not data:
        return {"message": "No circular processed yet. Run the pipeline first."}
    return data
