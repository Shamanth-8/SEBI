"""
Compliance Copilot — Tier 4
Generates a structured Compliance Summary after each pipeline run.
Answers: What changed? Why? Who's affected? What to do first?
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_copilot_summary(
    circular_id: str,
    circular_title: str,
    diff_result,
    compliance_mappings: Dict[str, Any],
    impact_propagation: Dict[str, Any],
    actions: List[Any],
    compliance_scores: Dict[str, float],
) -> Dict[str, Any]:
    """
    Generate a structured Compliance Summary card.
    Pure aggregation — no LLM call. Called from orchestrator after pipeline.
    """
    new_count = len(diff_result.new_obligations)
    mod_count = len(diff_result.modified_obligations)
    sup_count = len(diff_result.superseded_obligations)

    # Affected intermediaries: any that have at least one applicable obligation
    affected_intermediaries = list(compliance_mappings.keys())

    # Departments impacted (union of all action departments)
    departments = sorted(set(a.department for a in actions)) if actions else []

    # Top 3 immediate actions (critical/high priority)
    top_actions = [
        {
            "action_id": a.action_id,
            "title": a.title,
            "department": a.department,
            "priority": a.priority,
            "due_date": a.due_date,
            "days_remaining": a.days_remaining,
        }
        for a in sorted(
            actions,
            key=lambda x: ({"critical": 0, "high": 1, "medium": 2, "low": 3}.get(x.priority, 9),
                           x.days_remaining or 9999),
        )[:3]
    ]

    # Effort estimate
    total_actions = len(actions)
    critical_count = sum(1 for a in actions if a.priority == "critical")
    high_count = sum(1 for a in actions if a.priority == "high")
    estimated_days = critical_count * 3 + high_count * 2 + (total_actions - critical_count - high_count) * 1

    # What changed summary
    what_changed = []
    for obl in diff_result.new_obligations[:3]:
        what_changed.append(f"NEW: {obl.title}")
    for mod in diff_result.modified_obligations[:2]:
        obl = mod.get("new_obligation")
        if obl:
            what_changed.append(f"MODIFIED: {obl.title}")
    for sid in diff_result.superseded_obligations[:2]:
        what_changed.append(f"SUPERSEDED: {sid}")

    return {
        "circular_id": circular_id,
        "circular_title": circular_title,
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "what_changed": what_changed,
            "new_obligations": new_count,
            "modified_obligations": mod_count,
            "superseded_obligations": sup_count,
            "total_tasks_created": total_actions,
        },
        "affected_intermediaries": affected_intermediaries,
        "departments_impacted": departments,
        "top_3_immediate_actions": top_actions,
        "effort_estimate": {
            "estimated_implementation_days": estimated_days,
            "critical_tasks": critical_count,
            "high_tasks": high_count,
            "note": "Estimate based on task count and priority; actual effort may vary.",
        },
        "compliance_scores_before_after": compliance_scores,
        "total_affected_obligations": impact_propagation.get("total_affected_count", 0),
    }
