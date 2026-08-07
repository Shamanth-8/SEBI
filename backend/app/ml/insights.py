"""
Pre-AI document intelligence.

Everything in this module is computed from the document itself plus the trained
classifier — no LLM. It runs in well under a second and gives the analyst a
grounded picture (what kind of document is this, how many obligations, which
themes, which deadlines) *before* any generative model is asked for an opinion.
The LLM layer then works on top of these numbers instead of inventing its own.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from app.ml.extractor import _find_deadline, extract_obligations_ml, iter_units
from app.ml.model import RegGraphModel
from app.ml.textutil import clean_text, split_sentences

# Language that signals a binding requirement vs. a discretionary one.
MANDATORY_MARKERS = ["shall", "must", "is required to", "are required to",
                     "mandatory", "obliged to"]
PROHIBITION_MARKERS = ["shall not", "must not", "no ", "prohibited", "shall refrain"]
DISCRETIONARY_MARKERS = ["may", "should", "is encouraged", "endeavour", "best effort"]

FAMILY_LABELS = {
    "cyber_security": "Cyber Security & Resilience",
    "surveillance": "Market Surveillance",
    "kyc_onboarding": "KYC & Client Onboarding",
    "margin_risk": "Margin & Risk Management",
    "investor_grievance": "Investor Grievance Redressal",
    "outsourcing_bcp": "Outsourcing & Business Continuity",
}

_REF_RE = re.compile(
    r'SEBI[/\s]?(?:HO)?[/\s]?[A-Z]{2,6}[/\-][A-Z0-9/\-()\.]{5,60}', re.IGNORECASE)
_DATE_ANY_RE = re.compile(
    r'\b(?:\d{1,2}(?:st|nd|rd|th)?\s+)?'
    r'(?:January|February|March|April|May|June|July|August|September|October|'
    r'November|December)\s+\d{1,2}?,?\s*\d{4}\b', re.IGNORECASE)
_MONEY_RE = re.compile(r'(?:Rs\.?|INR|₹)\s?[\d,]+(?:\.\d+)?\s?(?:crore|lakh|million|billion)?',
                       re.IGNORECASE)
_SECTION_REF_RE = re.compile(
    r'\b(?:Section|Regulation|Rule|Clause|Chapter)\s+\d+[A-Za-z0-9()\.\-]*', re.IGNORECASE)

_STOP = set("""the of and to in for a an by with on such any its that this as or be is are from all
every not which may at it has have under within their there been than into each shall must
be been being upon there under other same time date manner respect case where when who whom
provided further hereby thereof therein shall_not""".split())


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def _count_markers(low: str, markers: List[str]) -> Dict[str, int]:
    return {m.strip(): low.count(m) for m in markers if low.count(m)}


def _days_until(deadline: str) -> Optional[int]:
    """Parse a fixed deadline into days remaining; None when not a fixed date."""
    for fmt in ("%B %d, %Y", "%B %d %Y", "%d %B %Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            d = datetime.strptime(deadline.strip(), fmt).date()
            return (d - date.today()).days
        except ValueError:
            continue
    return None


def document_profile(text: str, pages: int = 0) -> Dict:
    """Structural statistics — no model involved."""
    cleaned = clean_text(text)
    sentences = split_sentences(cleaned)
    words = _word_count(cleaned)
    low = cleaned.lower()

    lengths = [len(s.split()) for s in sentences] or [0]
    paragraphs = [p for p in re.split(r'\n\s*\n', cleaned) if p.strip()]

    refs = list(dict.fromkeys(m.group(0).strip() for m in _REF_RE.finditer(cleaned)))
    dates = list(dict.fromkeys(m.group(0).strip() for m in _DATE_ANY_RE.finditer(cleaned)))
    amounts = list(dict.fromkeys(m.group(0).strip() for m in _MONEY_RE.finditer(cleaned)))
    legal_refs = list(dict.fromkeys(m.group(0).strip() for m in _SECTION_REF_RE.finditer(cleaned)))

    return {
        "pages": pages,
        "characters": len(cleaned),
        "words": words,
        "sentences": len(sentences),
        "paragraphs": len(paragraphs),
        "avg_sentence_words": round(sum(lengths) / len(lengths), 1),
        "longest_sentence_words": max(lengths),
        "reading_time_minutes": max(1, round(words / 220)),
        "mandatory_language": _count_markers(low, MANDATORY_MARKERS),
        "prohibition_language": _count_markers(low, PROHIBITION_MARKERS),
        "discretionary_language": _count_markers(low, DISCRETIONARY_MARKERS),
        "circular_references": refs[:10],
        "dates_mentioned": dates[:12],
        "amounts_mentioned": amounts[:8],
        "legal_references": legal_refs[:12],
    }


def keyword_profile(text: str, top_n: int = 18) -> List[Dict]:
    """Most frequent domain terms (unigrams + bigrams), stopwords removed."""
    words = [w for w in re.findall(r"[a-zA-Z][a-zA-Z-]{2,}", text.lower()) if w not in _STOP]
    uni = Counter(words)
    bigrams = Counter(
        f"{a} {b}" for a, b in zip(words, words[1:])
        if a not in _STOP and b not in _STOP
    )
    merged = Counter()
    for term, n in bigrams.items():
        if n >= 3:
            merged[term] = n * 2          # weight phrases above single words
    for term, n in uni.items():
        if n >= 3:
            merged[term] += n
    return [{"term": t, "count": n} for t, n in merged.most_common(top_n)]


def section_profile(text: str) -> List[Dict]:
    """Obligation-bearing weight per section, from clause structure alone."""
    counts: Dict[str, Dict[str, int]] = defaultdict(lambda: {"sentences": 0, "mandatory": 0})
    for u in iter_units(text):
        s = u["section"]
        counts[s]["sentences"] += 1
        if any(m in u["sentence"].lower() for m in MANDATORY_MARKERS):
            counts[s]["mandatory"] += 1
    return [
        {"section": k[:70], "sentences": v["sentences"], "mandatory_sentences": v["mandatory"]}
        for k, v in counts.items() if v["sentences"] > 0
    ]


def analyze(
    text: str,
    pages: int = 0,
    circular_id: str = "PREVIEW",
    circular_title: str = "",
    intermediary_types: Optional[List[str]] = None,
    threshold: float = 0.55,
) -> Dict:
    """
    Full pre-AI analysis of a circular.

    Returns recognition + statistics + model-derived distributions + a set of
    plain-English findings, all chart-ready for the dashboard.
    """
    profile = document_profile(text, pages=pages)
    result: Dict = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "circular_id": circular_id,
        "circular_title": circular_title,
        "document_profile": profile,
        "keywords": keyword_profile(text),
        "sections": section_profile(text),
        "model_available": RegGraphModel.available(),
    }

    if not RegGraphModel.available():
        result["recognition"] = {"verdict": "Model not trained — run scripts/train_model.py"}
        result["findings"] = _rule_findings(profile, [], None)
        return result

    model = RegGraphModel.get()
    recognition = model.recognize_document(text)
    recognition["family_label"] = FAMILY_LABELS.get(recognition.get("family") or "",
                                                    recognition.get("family"))
    result["recognition"] = recognition

    obligations, diagnostics = extract_obligations_ml(
        text, circular_id or "PREVIEW", circular_title,
        intermediary_types=intermediary_types, threshold=threshold, model=model,
    )
    result["diagnostics"] = diagnostics
    result["obligations_preview"] = [
        {
            "obligation_id": o.obligation_id,
            "title": o.title,
            "description": o.description,
            "clause_reference": o.clause_reference,
            "severity": o.severity,
            "confidence": o.confidence_score,
            "deadline": o.deadline,
            "deadline_type": o.deadline_type,
            "responsible_party": o.responsible_party,
            "intermediary_types": o.intermediary_types,
            "evidence_requirements": o.evidence_requirements,
            "rationale": o.extraction_rationale,
        }
        for o in obligations
    ]

    # ── Distributions for charts ──────────────────────────────────────────
    sev = Counter(o.severity for o in obligations)
    dl = Counter(o.deadline_type or "not_specified" for o in obligations)
    itypes = Counter(t for o in obligations for t in o.intermediary_types)
    parties = Counter(o.responsible_party for o in obligations)
    conf_buckets = Counter()
    for o in obligations:
        b = "0.9–1.0" if o.confidence_score >= 0.9 else \
            "0.8–0.9" if o.confidence_score >= 0.8 else \
            "0.7–0.8" if o.confidence_score >= 0.7 else \
            "0.6–0.7" if o.confidence_score >= 0.6 else "0.55–0.6"
        conf_buckets[b] += 1

    result["distributions"] = {
        "severity": dict(sev),
        "deadline_type": dict(dl),
        "intermediary_types": dict(itypes.most_common()),
        "responsible_parties": dict(parties.most_common(8)),
        "confidence_buckets": dict(sorted(conf_buckets.items())),
    }

    # ── Deadline calendar ─────────────────────────────────────────────────
    calendar = []
    for o in obligations:
        if not o.deadline:
            continue
        days = _days_until(o.deadline) if o.deadline_type == "fixed" else None
        calendar.append({
            "obligation_id": o.obligation_id,
            "title": o.title,
            "deadline": o.deadline,
            "deadline_type": o.deadline_type,
            "days_remaining": days,
            "severity": o.severity,
        })
    calendar.sort(key=lambda c: (c["days_remaining"] is None, c["days_remaining"] or 0))
    result["deadline_calendar"] = calendar

    obl_density = round(len(obligations) / max(profile["sentences"], 1) * 100, 1)
    result["summary_metrics"] = {
        "obligations_detected": len(obligations),
        "obligation_density_pct": obl_density,
        "high_severity": sev.get("high", 0),
        "with_deadline": sum(1 for o in obligations if o.deadline),
        "without_deadline": sum(1 for o in obligations if not o.deadline),
        "recurring_obligations": dl.get("recurring", 0),
        "prohibitions": sum(1 for o in obligations
                            if any(p in o.description.lower() for p in PROHIBITION_MARKERS[:2])),
        "distinct_owners": len(parties),
        "mean_confidence": diagnostics.get("mean_confidence", 0.0),
    }

    result["findings"] = _rule_findings(profile, obligations, recognition,
                                        result["summary_metrics"], result["distributions"])
    return result


def _rule_findings(profile: Dict, obligations: List, recognition: Optional[Dict],
                   metrics: Optional[Dict] = None,
                   distributions: Optional[Dict] = None) -> List[Dict]:
    """
    Plain-English observations derived only from counts.

    These are deliberately deterministic: the same document always produces the
    same findings, which is what makes them usable as an audit baseline against
    the LLM's narrative.
    """
    out: List[Dict] = []

    def add(level: str, title: str, detail: str):
        out.append({"level": level, "title": title, "detail": detail})

    if recognition:
        if not recognition.get("is_circular"):
            add("warning", "Document type not recognised",
                f"The recogniser scored this {recognition.get('circular_confidence', 0):.0%} "
                "likely to be a SEBI-style circular. Downstream extraction may be unreliable.")
        elif recognition.get("is_novel_topic"):
            add("info", "Subject matter outside the trained families",
                f"Closest known family is "
                f"{FAMILY_LABELS.get(recognition.get('family',''), recognition.get('family'))} "
                f"but similarity is only "
                f"{1 - recognition.get('novelty', 1):.0%}. Obligation detection still applies; "
                "theme-specific labels should be treated as indicative.")
        else:
            add("success", "Circular recognised",
                f"Matched **{FAMILY_LABELS.get(recognition.get('family',''), '')}** with "
                f"{recognition.get('family_confidence', 0):.0%} confidence "
                f"({recognition.get('circular_confidence', 0):.0%} confidence it is a circular).")

    if metrics:
        add("info", f"{metrics['obligations_detected']} obligations detected",
            f"{metrics['obligation_density_pct']}% of the sentences in this document carry a "
            f"binding requirement; mean model confidence {metrics['mean_confidence']:.2f}.")

        if metrics["high_severity"]:
            add("warning", f"{metrics['high_severity']} high-severity obligations",
                "These drive the risk score and should be assigned owners first.")

        if metrics["without_deadline"]:
            add("warning", f"{metrics['without_deadline']} obligations have no stated deadline",
                "No timeline was found in the clause text — a target date must be set manually, "
                "otherwise they will never surface in the urgency queue.")

        if metrics["recurring_obligations"]:
            add("info", f"{metrics['recurring_obligations']} recurring obligations",
                "These need a standing calendar entry rather than a one-off task.")

        if metrics["prohibitions"]:
            add("warning", f"{metrics['prohibitions']} prohibitions ('shall not')",
                "Prohibitions are controls to monitor continuously, not tasks to close.")

        if metrics["distinct_owners"] > 4:
            add("info", f"Ownership spans {metrics['distinct_owners']} roles",
                "Cross-functional coordination will be needed to close this circular.")

    md = profile.get("mandatory_language", {})
    dsc = profile.get("discretionary_language", {})
    n_mand, n_disc = sum(md.values()), sum(dsc.values())
    if n_mand or n_disc:
        add("info", "Language profile",
            f"{n_mand} mandatory markers (shall/must/required) vs {n_disc} discretionary "
            f"(may/should). "
            + ("Predominantly binding text." if n_mand > n_disc * 2
               else "A meaningful share of the text is advisory — read those clauses before "
                    "committing effort."))

    if profile.get("circular_references"):
        add("info", f"References {len(profile['circular_references'])} other circular(s)",
            "Superseded or amended obligations may exist in the graph: "
            + ", ".join(profile["circular_references"][:3]))

    if profile.get("avg_sentence_words", 0) > 34:
        add("info", "Dense drafting",
            f"Average sentence is {profile['avg_sentence_words']} words. Long clauses often "
            "bundle several obligations — check the low-confidence rejects.")

    if distributions:
        itypes = distributions.get("intermediary_types") or {}
        if itypes:
            top = max(itypes.items(), key=lambda kv: kv[1])
            add("info", f"Primary impact: {top[0].replace('_', ' ')}",
                f"{top[1]} of the obligations name this intermediary type explicitly.")

    return out
