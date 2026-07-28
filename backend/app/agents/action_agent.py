"""
Operational Action Agent — Tier 1A
Transforms classified obligations into structured, executable ComplianceAction tasks.
"""
import logging
from datetime import datetime, date
from typing import List, Optional, Dict
import re

from app.models.obligation import Obligation, ComplianceAction

logger = logging.getLogger(__name__)

# Maps responsible_party keywords → department
_DEPT_MAP = {
    "compliance": "Compliance",
    "risk": "Risk Management",
    "trading": "Trading Operations",
    "board": "Board / Senior Management",
    "legal": "Legal",
    "technology": "Technology / IT",
    "audit": "Internal Audit",
    "operations": "Operations",
    "surveillance": "Surveillance",
    "finance": "Finance",
    "depository": "Depository Operations",
    "registrar": "Registrar & Transfer",
}

_PRIORITY_MAP = {
    ("high", "fixed"):      "critical",
    ("high", "recurring"):  "high",
    ("high", "relative"):   "critical",
    ("high", "not_specified"): "high",
    ("medium", "fixed"):    "high",
    ("medium", "recurring"):"medium",
    ("medium", "relative"): "high",
    ("medium", "not_specified"): "medium",
    ("low", "fixed"):       "medium",
    ("low", "recurring"):   "low",
    ("low", "relative"):    "medium",
    ("low", "not_specified"): "low",
}

_ACTION_COUNTER = 0


def _next_action_id() -> str:
    global _ACTION_COUNTER
    _ACTION_COUNTER += 1
    return f"ACT-{_ACTION_COUNTER:05d}"


def _infer_department(responsible_party: str) -> str:
    rp_lower = responsible_party.lower()
    for kw, dept in _DEPT_MAP.items():
        if kw in rp_lower:
            return dept
    return "Compliance"  # default


def _compute_days_remaining(deadline: Optional[str], deadline_type: Optional[str]) -> Optional[int]:
    """
    Parse deadline string and return days remaining from today.
    Handles ISO dates, relative expressions ("within 30 days"), recurring labels.
    """
    if not deadline:
        return None
    today = date.today()

    # ISO date pattern e.g. 2025-12-31
    iso_match = re.search(r"(\d{4}-\d{2}-\d{2})", deadline)
    if iso_match:
        try:
            due = date.fromisoformat(iso_match.group(1))
            return (due - today).days
        except ValueError:
            pass

    # "within N days" pattern
    within_match = re.search(r"within\s+(\d+)\s+(?:working\s+)?days?", deadline, re.I)
    if within_match:
        return int(within_match.group(1))

    # "N days" standalone
    num_match = re.search(r"(\d+)\s+(?:working\s+)?days?", deadline, re.I)
    if num_match:
        return int(num_match.group(1))

    # Monthly / quarterly / recurring — treat as 30 / 90
    if re.search(r"monthly|every month", deadline, re.I):
        return 30
    if re.search(r"quarterly", deadline, re.I):
        return 90
    if re.search(r"annual|yearly", deadline, re.I):
        return 365
    if deadline_type == "recurring":
        return 30  # safe default for recurring

    return None


def generate_compliance_actions(
    obligations: List[Obligation],
    intermediary_type: str = "stockbroker",
) -> List[ComplianceAction]:
    """
    Generate a ComplianceAction task for each applicable obligation.
    Pure deterministic logic — no LLM call needed.
    """
    actions: List[ComplianceAction] = []

    for obl in obligations:
        # Only for applicable intermediary types
        if intermediary_type not in obl.intermediary_types:
            continue

        days = _compute_days_remaining(obl.deadline, obl.deadline_type)
        overdue = (days is not None and days < 0)

        # Priority boost if overdue
        base_priority = _PRIORITY_MAP.get(
            (obl.severity, obl.deadline_type or "not_specified"),
            "medium"
        )
        if overdue:
            base_priority = "critical"
        elif days is not None and days <= 7:
            if base_priority in ("medium", "low"):
                base_priority = "high"

        dept = _infer_department(obl.responsible_party)

        action = ComplianceAction(
            action_id=_next_action_id(),
            obligation_id=obl.obligation_id,
            circular_id=obl.circular_id,
            department=dept,
            owner=obl.responsible_party or "Compliance Officer",
            priority=base_priority,
            due_date=obl.deadline,
            days_remaining=days,
            overdue=overdue,
            title=f"[{base_priority.upper()}] {obl.title}",
            description=obl.description,
            steps=_default_steps(obl),
            evidence_required=obl.evidence_requirements,
            dependencies=obl.related_obligations[:5],
            status="overdue" if overdue else "open",
        )
        actions.append(action)

    # Sort: critical first, then by days_remaining ascending (soonest first)
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    def sort_key(a: ComplianceAction):
        days = a.days_remaining if a.days_remaining is not None else 9999
        return (priority_order.get(a.priority, 9), days)

    actions.sort(key=sort_key)
    return actions


def _default_steps(obl: Obligation) -> List[str]:
    """Generate default 5-step SOP from obligation fields."""
    return [
        f"Step 1: Review {obl.clause_reference} in the source circular and confirm applicability.",
        f"Step 2: {obl.required_action or 'Implement the required changes per the obligation.'}",
        f"Step 3: Update internal policy / procedures to reflect new requirement.",
        f"Step 4: Collect and document evidence: {', '.join(obl.evidence_requirements[:3]) or 'as applicable'}.",
        f"Step 5: Submit completed checklist to {obl.responsible_party or 'Compliance Officer'} for sign-off.",
    ]
