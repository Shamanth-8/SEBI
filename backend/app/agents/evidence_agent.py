"""
Evidence Matching Agent — Track 1
Replaces keyword overlap scoring with LLM-based semantic evidence matching.

For each evidence_requirement of an obligation, the agent judges whether the
uploaded document actually satisfies it — returning a per-requirement score,
reasoning, and an overall match assessment.
"""
import json
import logging
import re
from typing import List, Dict, Any, Optional
from app.config import get_settings

logger = logging.getLogger(__name__)


def match_evidence(
    document_text: str,
    obligation_title: str,
    obligation_description: str,
    evidence_requirements: List[str],
    clause_reference: str = "",
) -> Dict[str, Any]:
    """
    Use LLM to semantically match an uploaded document against an obligation's
    evidence requirements.

    Returns:
        {
            "overall_score":   float 0-1,
            "evidence_status": "green" | "yellow" | "red",
            "matched":         [list of satisfied requirement strings],
            "unmatched":       [list of unsatisfied requirement strings],
            "per_requirement": [
                {
                    "requirement": str,
                    "satisfied":   bool,
                    "score":       float 0-1,
                    "reasoning":   str,
                }
            ],
            "overall_reasoning": str,
            "method": "llm" | "keyword_fallback",
        }
    """
    if not evidence_requirements:
        return _empty_result()

    # Truncate document to first 4000 chars to fit token budget
    doc_snippet = document_text[:4000].strip()
    if len(document_text) > 4000:
        doc_snippet += "\n... [document truncated for analysis]"

    try:
        settings = get_settings()
        from app.anthropic_adapter import create_anthropic_compatible_client
        client = create_anthropic_compatible_client(settings.LLM_PROVIDER)

        requirements_block = "\n".join(
            f"{i+1}. {req}" for i, req in enumerate(evidence_requirements)
        )

        prompt = f"""You are a SEBI compliance auditor reviewing whether an uploaded document satisfies evidence requirements for a regulatory obligation.

OBLIGATION:
- Title: {obligation_title}
- Description: {obligation_description[:400]}
- Clause Reference: {clause_reference}

EVIDENCE REQUIREMENTS (what must be proven):
{requirements_block}

UPLOADED DOCUMENT (excerpt):
---
{doc_snippet}
---

For each evidence requirement, assess whether the uploaded document satisfies it.
Consider semantic meaning — a "board resolution" satisfies "evidence of board-level approval" even if those exact words differ.

Return ONLY a valid JSON object with this exact structure:
{{
  "per_requirement": [
    {{
      "requirement": "exact requirement text",
      "satisfied": true or false,
      "score": 0.0 to 1.0,
      "reasoning": "one sentence explaining why satisfied or not"
    }}
  ],
  "overall_reasoning": "2-3 sentence summary of the document's coverage of these requirements"
}}"""

        msg = client.messages.create(
            model=settings.LLM_MODEL,
            max_tokens=900,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()

        # Extract JSON
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            raise ValueError("No JSON object found in LLM response")

        parsed = json.loads(m.group())
        per_req = parsed.get("per_requirement", [])
        overall_reasoning = parsed.get("overall_reasoning", "")

        # Build matched / unmatched lists
        matched   = [r["requirement"] for r in per_req if r.get("satisfied")]
        unmatched = [r["requirement"] for r in per_req if not r.get("satisfied")]

        # Overall score = average of individual scores
        scores = [r.get("score", 1.0 if r.get("satisfied") else 0.0) for r in per_req]
        overall_score = round(sum(scores) / len(scores), 3) if scores else 0.0

        # Determine status
        if overall_score >= 0.80:
            status = "green"
        elif overall_score >= 0.40:
            status = "yellow"
        else:
            status = "red"

        logger.info(
            f"LLM evidence match: score={overall_score} status={status} "
            f"matched={len(matched)}/{len(evidence_requirements)}"
        )

        return {
            "overall_score":     overall_score,
            "evidence_status":   status,
            "matched":           matched,
            "unmatched":         unmatched,
            "per_requirement":   per_req,
            "overall_reasoning": overall_reasoning,
            "method":            "llm",
        }

    except Exception as e:
        logger.warning(f"LLM evidence matching failed ({e}); falling back to keyword match")
        return _keyword_fallback(document_text, evidence_requirements)


# ─── Keyword fallback (original logic, kept as safety net) ───────────────────

def _keyword_fallback(
    document_text: str,
    evidence_requirements: List[str],
) -> Dict[str, Any]:
    """Original keyword overlap matching — used when LLM is unavailable."""
    text_lower = document_text.lower()
    per_req = []
    matched = []
    unmatched = []

    for req in evidence_requirements:
        words = req.lower().split()
        hit_count = sum(1 for w in words if w in text_lower)
        score = round(hit_count / max(len(words), 1), 2)
        satisfied = score >= 0.5

        per_req.append({
            "requirement": req,
            "satisfied":   satisfied,
            "score":       score,
            "reasoning":   (
                f"Keyword match: {hit_count}/{len(words)} words found in document."
                if satisfied
                else f"Only {hit_count}/{len(words)} keywords matched — document may not cover this requirement."
            ),
        })
        (matched if satisfied else unmatched).append(req)

    overall_score = round(len(matched) / max(len(evidence_requirements), 1), 3)
    status = "green" if overall_score >= 0.8 else "yellow" if overall_score >= 0.4 else "red"

    return {
        "overall_score":     overall_score,
        "evidence_status":   status,
        "matched":           matched,
        "unmatched":         unmatched,
        "per_requirement":   per_req,
        "overall_reasoning": f"Keyword analysis: {len(matched)} of {len(evidence_requirements)} requirements matched.",
        "method":            "keyword_fallback",
    }


def _empty_result() -> Dict[str, Any]:
    return {
        "overall_score":     0.0,
        "evidence_status":   "red",
        "matched":           [],
        "unmatched":         [],
        "per_requirement":   [],
        "overall_reasoning": "No evidence requirements defined for this obligation.",
        "method":            "none",
    }
