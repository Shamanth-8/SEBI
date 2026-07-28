"""
SOP Generator Agent — Tier 2C
Generates numbered Standard Operating Procedures for obligations/tasks.
Uses LLM for richer output; falls back to deterministic template if LLM unavailable.
"""
import logging
from typing import List, Optional
from app.models.obligation import Obligation
from app.config import get_settings

logger = logging.getLogger(__name__)


# ─── Deterministic template SOP ──────────────────────────────────────────────

def generate_sop_deterministic(obligation: Obligation) -> List[str]:
    """
    Template-based SOP generator — no LLM required.
    Always produces a clean, numbered 6-step procedure.
    """
    evidence_str = ", ".join(obligation.evidence_requirements[:3]) or "supporting documentation"
    action_str = obligation.required_action or "fulfil the stated requirement"
    owner_str = obligation.responsible_party or "Compliance Officer"
    deadline_str = obligation.deadline or "the applicable regulatory deadline"

    return [
        f"Step 1 — Review source clause: Read {obligation.clause_reference} "
        f"and confirm applicability to your organisation.",
        f"Step 2 — Gap assessment: Compare current policy/process against the requirement: "
        f"'{action_str}'. Document any gaps found.",
        f"Step 3 — Implement changes: Update internal policy, systems, or procedures "
        f"to satisfy the obligation. Notify affected teams.",
        f"Step 4 — Collect evidence: Gather required evidence — {evidence_str}. "
        f"Store in the compliance repository with date and version.",
        f"Step 5 — Review and approval: Submit evidence to {owner_str} for sign-off "
        f"before {deadline_str}.",
        f"Step 6 — Close and audit: Mark the obligation as complete in the compliance "
        f"register. Confirm the audit trail reflects completion.",
    ]


# ─── LLM-enhanced SOP ────────────────────────────────────────────────────────

def generate_sop(obligation: Obligation, use_llm: bool = False) -> List[str]:
    """
    Generate SOP for an obligation.
    use_llm=True attempts LLM enrichment; falls back to deterministic on any error.
    """
    if not use_llm:
        return generate_sop_deterministic(obligation)

    try:
        settings = get_settings()
        from app.anthropic_adapter import create_anthropic_compatible_client
        client = create_anthropic_compatible_client(settings.LLM_PROVIDER)

        prompt = f"""You are a regulatory compliance consultant. Generate a concise, practical
Standard Operating Procedure (SOP) for the following SEBI compliance obligation.

Obligation title: {obligation.title}
Clause reference: {obligation.clause_reference}
Required action: {obligation.required_action}
Responsible party: {obligation.responsible_party}
Deadline: {obligation.deadline or 'Not specified'}
Evidence required: {', '.join(obligation.evidence_requirements)}

Return EXACTLY 6 numbered steps as a JSON array of strings:
["Step 1 — ...", "Step 2 — ...", ..., "Step 6 — ..."]

Each step must be one sentence, actionable, specific. Return ONLY valid JSON array."""

        msg = client.messages.create(
            model=settings.LLM_MODEL,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        import json
        raw = msg.content[0].text
        # extract array
        import re
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if m:
            steps = json.loads(m.group())
            if isinstance(steps, list) and len(steps) >= 4:
                return steps
    except Exception as e:
        logger.warning(f"SOP LLM generation failed ({e}); using deterministic fallback")

    return generate_sop_deterministic(obligation)
