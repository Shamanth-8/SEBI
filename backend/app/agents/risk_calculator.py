"""
Compliance Gap Risk Score — Tier 1B
Pure weighted formula over existing Obligation fields.
No ML/model needed.

Formula:
  risk_score = severity_weight + evidence_weight + urgency_weight + dependency_weight

  severity_weight  : high=40, medium=20, low=5
  evidence_weight  : red/missing=30, yellow/partial=15, green/complete=0
  urgency_weight   : overdue=20, <=7 days=15, <=30 days=10, <=90 days=5, else=0
  dependency_weight: min(dep_count * 2, 10)   (capped at 10)

  risk_score is 0–100.
  label: 0-30 → Low, 31-65 → Medium, 66+ → High
"""
from __future__ import annotations
import logging
from datetime import date
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.obligation import Obligation

logger = logging.getLogger(__name__)

_SEVERITY_WEIGHTS = {"high": 40, "medium": 20, "low": 5}
_EVIDENCE_WEIGHTS = {"red": 30, "yellow": 15, "green": 0}


def _urgency_weight(days_remaining: Optional[int]) -> int:
    if days_remaining is None:
        return 0
    if days_remaining < 0:
        return 20
    if days_remaining <= 7:
        return 15
    if days_remaining <= 30:
        return 10
    if days_remaining <= 90:
        return 5
    return 0


def compute_risk_score(obligation: "Obligation", dep_count: int = 0) -> tuple[float, str]:
    """
    Returns (risk_score 0-100, label "Low"|"Medium"|"High").
    dep_count is the number of downstream obligations this one affects.
    """
    from app.agents.action_agent import _compute_days_remaining

    sev = _SEVERITY_WEIGHTS.get(obligation.severity, 20)
    ev = _EVIDENCE_WEIGHTS.get(obligation.evidence_status.value, 30)

    days = _compute_days_remaining(obligation.deadline, obligation.deadline_type)
    urg = _urgency_weight(days)

    dep = min(dep_count * 2, 10)

    score = float(min(sev + ev + urg + dep, 100))

    if score <= 30:
        label = "Low"
    elif score <= 65:
        label = "Medium"
    else:
        label = "High"

    return score, label


def enrich_obligation_risk(obligation: "Obligation", dep_count: int = 0) -> "Obligation":
    """
    Mutates obligation in-place: sets risk_score and risk_label.
    Returns the same object for chaining.
    """
    score, label = compute_risk_score(obligation, dep_count)
    obligation.risk_score = score
    obligation.risk_label = label
    return obligation


def enrich_all(graph) -> None:
    """
    Walk the full obligation graph and update risk scores for every node.
    Call this after any pipeline run or evidence update.
    """
    for obl_id, obl in graph.obligation_map.items():
        # obligation_map and the networkx graph can drift apart (an obligation
        # recorded but never added as a node, or a stale pickle). A missing node
        # means no known dependents — not a reason to abort the whole run.
        dep_count = (
            len(list(graph.graph.successors(obl_id)))
            if graph.graph.has_node(obl_id) else 0
        )
        enrich_obligation_risk(obl, dep_count)
