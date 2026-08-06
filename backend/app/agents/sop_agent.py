"""
SOP Generator Agent — Tier 2C
Generates numbered Standard Operating Procedures for obligations/tasks.
Uses LLM for richer, role-specific output; falls back to deterministic template if LLM unavailable.
"""
import json
import logging
import re
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
    action_str   = obligation.required_action or "fulfil the stated requirement"
    owner_str    = obligation.responsible_party or "Compliance Officer"
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

def generate_sop(
    obligation: Obligation,
    use_llm: bool = True,
    intermediary_type: Optional[str] = None,
) -> List[str]:
    """
    Generate SOP for an obligation.

    use_llm=True  → calls LLM for role-specific, context-aware steps.
    use_llm=False → deterministic template only.

    Falls back to deterministic on any LLM error so the pipeline never breaks.
    SOP is cached on the obligation node (obligation.sop_cache) to avoid
    repeated LLM calls for the same obligation.
    """
    # ── Return cached SOP if available ──────────────────────────────────────
    cache_attr = f"_sop_cache_{intermediary_type or 'default'}"
    cached = getattr(obligation, cache_attr, None)
    if cached:
        logger.debug(f"SOP cache hit for {obligation.obligation_id}")
        return cached

    if not use_llm:
        return generate_sop_deterministic(obligation)

    try:
        settings = get_settings()
        from app.anthropic_adapter import create_anthropic_compatible_client
        client = create_anthropic_compatible_client(settings.LLM_PROVIDER)

        # Build intermediary-specific context
        intermediary_context = ""
        if intermediary_type:
            profiles = {
                "stockbroker": "a SEBI-registered stockbroker with trading, settlement, margin, and surveillance operations",
                "depository":  "a SEBI-registered depository (NSDL/CDSL) handling demat accounts and securities transfers",
                "listed_company": "a listed company subject to SEBI LODR and insider trading regulations",
                "investment_adviser": "a SEBI-registered investment adviser providing portfolio advice to retail clients",
                "fiduciary": "a fiduciary / trustee managing client assets under SEBI regulations",
                "rta": "a Registrar and Transfer Agent (RTA) handling shareholder records and corporate actions",
            }
            desc = profiles.get(intermediary_type, intermediary_type)
            intermediary_context = f"\nThis SOP is for {desc}."

        evidence_str = (
            "\n".join(f"  - {r}" for r in obligation.evidence_requirements)
            if obligation.evidence_requirements
            else "  - Supporting documentation as applicable"
        )

        prompt = f"""You are a senior SEBI compliance consultant writing a Standard Operating Procedure (SOP) for a compliance team.{intermediary_context}

OBLIGATION DETAILS:
- Title: {obligation.title}
- Clause Reference: {obligation.clause_reference}
- Description: {obligation.description}
- Required Action: {obligation.required_action or "As described above"}
- Responsible Party: {obligation.responsible_party or "Compliance Officer"}
- Deadline: {obligation.deadline or "Not specified"} ({obligation.deadline_type or "not_specified"})
- Severity: {obligation.severity}
- Evidence Required:
{evidence_str}

Write a practical, numbered SOP with exactly 6 steps. Each step must:
1. Be role-specific and actionable (name the actual role/team)
2. Reference the actual obligation content (not generic language)
3. Specify what document/record to create or update
4. Be one to two clear sentences

Return ONLY a valid JSON array of 6 strings, like:
["Step 1 — ...", "Step 2 — ...", "Step 3 — ...", "Step 4 — ...", "Step 5 — ...", "Step 6 — ..."]

No markdown, no explanation, no extra keys — just the JSON array."""

        msg = client.messages.create(
            model=settings.LLM_MODEL,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()

        # Extract JSON array robustly
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if m:
            steps = json.loads(m.group())
            if isinstance(steps, list) and len(steps) >= 4:
                logger.info(f"LLM SOP generated for {obligation.obligation_id} ({len(steps)} steps)")
                # Cache on obligation object
                try:
                    object.__setattr__(obligation, cache_attr, steps)
                except Exception:
                    pass  # Pydantic model — cache miss is acceptable
                return steps

        logger.warning(f"LLM SOP response unparseable for {obligation.obligation_id}; using fallback")

    except Exception as e:
        logger.warning(f"SOP LLM generation failed for {obligation.obligation_id} ({e}); using deterministic fallback")

    return generate_sop_deterministic(obligation)
