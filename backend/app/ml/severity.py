"""
Severity assessment — rules first, model second.

The trained severity head scores ~0.52 on held-out templates and drifts badly on
out-of-distribution text: on the real 399-page stock broker master circular it
labelled 72% of obligations "high", which no compliance officer would accept.

Severity in regulatory drafting has strong surface signals, though — a prohibition
is serious, a hard reporting deadline to the regulator is serious, a record-keeping
requirement usually is not. So the rules decide when they fire, the model decides
only when they do not, and the result carries `basis` so the UI can say which one
spoke.
"""
from __future__ import annotations

import re
from typing import Dict, Optional, Tuple

# ── HIGH: things that get an intermediary fined or barred ────────────────────
_HIGH_PATTERNS: Dict[str, str] = {
    "prohibition": r'\b(shall not|must not|shall refrain|is prohibited|are prohibited|'
                   r'no\s+\w+(?:\s+\w+)?\s+shall|under no circumstance)\b',
    "client_assets": r'\b(client funds|clients.{0,3} funds|client securities|segregat|'
                     r'misuse|misutilisation|proprietary (?:trades?|obligations?)|'
                     r'net worth|margin)\b',
    "regulator_reporting": r'\b(report(?:ing)? to (?:sebi|the board|the exchange)|'
                           r'shall (?:report|intimate|inform|notify) (?:sebi|the board)|'
                           r'suspicious transaction|str\b|intimate the board)\b',
    "penalty": r'\b(penalt|liable|liability|disciplinary|enforcement action|'
               r'financial disincentive|shall be deemed to have violated)\b',
    "immediacy": r'\b(immediately|forthwith|without any delay|same day|'
                 r'not later than the next (?:working )?day)\b',
    "fraud_integrity": r'\b(manipulat|insider trading|unpublished price sensitive|'
                       r'front running|money laundering|fictitious|benami)\b',
    "cyber_critical": r'\b(cyber (?:attack|incident|breach)|unauthorised access|'
                      r'data breach|encrypt)\b',
}

# ── LOW: housekeeping and advisory text ──────────────────────────────────────
_LOW_PATTERNS: Dict[str, str] = {
    "discretionary": r'\b(may (?:consider|choose|opt)|is encouraged|are encouraged|'
                     r'endeavour|best effort|as far as possible|desirable)\b',
    "awareness": r'\b(awareness programme|training programme|educat|publicis|'
                 r'disseminate|display on its website)\b',
    "administrative": r'\b(format (?:is )?(?:prescribed|enclosed)|nomenclature|'
                      r'for the sake of|clarif|guidance of)\b',
}

_HIGH_RE = {k: re.compile(v, re.IGNORECASE) for k, v in _HIGH_PATTERNS.items()}
_LOW_RE = {k: re.compile(v, re.IGNORECASE) for k, v in _LOW_PATTERNS.items()}

# A hard deadline is an escalator, not a decider on its own.
_HARD_DEADLINE = {"relative", "fixed"}


def assess_severity(
    sentence: str,
    deadline_type: Optional[str] = None,
    model_severity: Optional[str] = None,
    model_confidence: float = 0.0,
) -> Tuple[str, str]:
    """
    Return (severity, basis).

    `basis` names what decided it — a rule id, or "model" — so the dashboard can
    show why an obligation is rated the way it is instead of asserting a number.
    """
    high_hits = [name for name, rx in _HIGH_RE.items() if rx.search(sentence)]
    low_hits = [name for name, rx in _LOW_RE.items() if rx.search(sentence)]

    if high_hits:
        return "high", f"rule: {', '.join(high_hits[:2])}"

    # A binding deadline plus an explicit obligation is at least medium; combined
    # with a second escalator it is high.
    has_hard_deadline = (deadline_type or "") in _HARD_DEADLINE

    if low_hits and not has_hard_deadline:
        return "low", f"rule: {', '.join(low_hits[:2])}"

    if has_hard_deadline:
        return "medium", "rule: hard deadline, no escalating factor"

    # Nothing decisive on the surface — defer to the model, but only when it is
    # confident. Its calibration off-distribution does not justify more than that.
    if model_severity and model_confidence >= 0.60:
        return model_severity, f"model ({model_confidence:.2f})"

    return "medium", "default (no decisive signal)"
