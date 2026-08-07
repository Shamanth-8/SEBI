"""
LLM insight layer — the second pass, on top of the local model's numbers.

The deterministic analysis (app.ml.insights) has already answered *what is in the
document*. This agent is given those figures and asked only for the judgement a
model is actually good at: what it means, what to do first, and what is ambiguous.

It never sees the raw circular alone — it sees the extracted obligations and the
computed metrics, so its narrative cannot drift away from the audited numbers.
A failure here degrades the run to "statistics only"; it never fails the pipeline.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Dict, List, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)


def _compact_obligations(obligations: List, limit: int = 25) -> List[Dict]:
    """Highest-severity, highest-confidence first — the LLM has a token budget."""
    rank = {"high": 0, "medium": 1, "low": 2}
    ordered = sorted(
        obligations,
        key=lambda o: (rank.get(o.severity, 3), -getattr(o, "confidence_score", 0.0)),
    )
    return [
        {
            "id": o.obligation_id,
            "title": o.title[:110],
            "severity": o.severity,
            "deadline": o.deadline,
            "owner": o.responsible_party[:60],
            "applies_to": o.intermediary_types,
        }
        for o in ordered[:limit]
    ]


def generate_ai_insights(
    circular_id: str,
    circular_title: str,
    pre_ai: Dict,
    obligations: List,
    diff_summary: Optional[Dict] = None,
) -> Dict:
    """
    Returns {available, insights|error, model}. `available=False` means the caller
    should show the deterministic findings alone — not that the run failed.
    """
    settings = get_settings()

    metrics = pre_ai.get("summary_metrics", {})
    recognition = pre_ai.get("recognition", {})
    distributions = pre_ai.get("distributions", {})
    findings = [f"{f['title']}: {f['detail']}" for f in pre_ai.get("findings", [])][:8]

    grounding = {
        "recognition": {
            "verdict": recognition.get("verdict"),
            "family": recognition.get("family"),
            "family_confidence": recognition.get("family_confidence"),
            "novel_topic": recognition.get("is_novel_topic"),
        },
        "metrics": metrics,
        "distributions": distributions,
        "deterministic_findings": findings,
        "diff": diff_summary or {},
        "obligations": _compact_obligations(obligations),
    }

    prompt = f"""You are a senior SEBI compliance advisor briefing a compliance head.

A circular has already been analysed by a deterministic pipeline. Here are its verified outputs —
these numbers are correct; do not recompute, contradict or restate them at length:

{json.dumps(grounding, indent=2, default=str)[:7000]}

Circular: {circular_title or circular_id}

Write the judgement layer the numbers cannot provide. Return ONLY valid JSON, no markdown fences:

{{
  "executive_summary": "3-4 sentences: what this circular does and why it matters operationally",
  "key_risks": [
    {{"risk": "short risk statement", "why": "the specific consequence of getting it wrong",
      "obligation_ids": ["id1"]}}
  ],
  "first_30_days": ["concrete action 1", "concrete action 2", "concrete action 3"],
  "ambiguities": ["a clause that is genuinely unclear and why it matters"],
  "questions_for_the_regulator": ["a precise question worth raising"],
  "effort_view": "1-2 sentences on where the real effort sits"
}}

Rules:
- Ground every claim in the obligations listed above; cite obligation ids where relevant.
- 3-5 items in key_risks, 3-5 in first_30_days, 0-3 in ambiguities and questions.
- No generic compliance advice ("maintain good records"). If the data doesn't support a
  section, return an empty list for it rather than filling space."""

    try:
        from app.anthropic_adapter import create_anthropic_compatible_client
        from app.llm_errors import call_with_retry

        client = create_anthropic_compatible_client(settings.LLM_PROVIDER)
        message = call_with_retry(
            lambda: client.messages.create(
                model=settings.LLM_MODEL,
                max_tokens=1600,
                messages=[{"role": "user", "content": prompt}],
            ),
            max_retries=settings.LLM_MAX_RETRIES,
            label="ai-insights",
        )
        raw = (message.content[0].text or "").strip()
        parsed = _parse_json_object(raw)
        if parsed is None:
            return {"available": False,
                    "error": f"Model returned unparseable output: {raw[:180]}",
                    "model": settings.LLM_MODEL}
        return {"available": True, "insights": parsed, "model": settings.LLM_MODEL}

    except Exception as exc:
        logger.warning(f"AI insights unavailable: {exc}")
        return {"available": False, "error": str(exc), "model": settings.LLM_MODEL}


def _parse_json_object(text: str) -> Optional[Dict]:
    """Tolerate code fences and leading prose, which smaller models routinely add."""
    candidate = (text or "").strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", candidate, re.DOTALL)
    if fence:
        candidate = fence.group(1).strip()
    for attempt in (candidate, None):
        if attempt is None:
            m = re.search(r'\{.*\}', candidate, re.DOTALL)
            if not m:
                return None
            attempt = m.group()
        try:
            parsed = json.loads(attempt)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None
