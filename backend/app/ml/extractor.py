"""
Model-driven obligation extraction — the offline half of the pipeline.

Turns raw circular text into `Obligation` objects using the trained classifier
plus deterministic field extraction (deadline, responsible party, action, evidence).
No network calls, so this path always works: the LLM later *enriches* these
obligations rather than being the only thing that can produce them.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, Iterable, List, Optional, Tuple

from app.models.obligation import (
    ChecklistItem, EvidenceStatus, Obligation, ObligationStatus,
)
from app.ml.model import RegGraphModel
from app.ml.severity import assess_severity
from app.ml.textutil import (
    clean_text, is_boilerplate, segment_blocks, split_sentences, strip_clause_number,
)

logger = logging.getLogger(__name__)

# ── Deterministic field extraction ───────────────────────────────────────────

_HEADING_RE = re.compile(
    r'^(?:\d+\.\s*[A-Z][A-Za-z ,&/()-]{3,70}|[A-Z][A-Z \-&/]{5,70})\s*$'
)

_NUM_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "fifteen": 15, "twenty": 20, "thirty": 30,
    "forty": 40, "forty-five": 45, "sixty": 60, "ninety": 90,
}

_RELATIVE_RE = re.compile(
    r'\bwithin\s+((?:\d+|' + "|".join(_NUM_WORDS) + r')(?:\s*-\s*\w+)?)\s+'
    r'(working\s+days?|business\s+days?|calendar\s+days?|days?|weeks?|months?|hours?)',
    re.IGNORECASE,
)
_FREQ_RE = re.compile(
    r'\b(daily|weekly|fortnightly|monthly|bi-monthly|quarterly|half-yearly|'
    r'semi-annually|annually|yearly|every\s+(?:calendar\s+)?(?:quarter|month|year)|'
    r'on\s+a\s+(?:daily|weekly|monthly|quarterly|half-yearly|annual)\s+basis|'
    r'at\s+the\s+end\s+of\s+every\s+calendar\s+quarter|continuous\s+basis)\b',
    re.IGNORECASE,
)
_DATE_RE = re.compile(
    r'\b(?:with\s+effect\s+from\s+|not\s+later\s+than\s+|on\s+or\s+before\s+)?'
    r'((?:\d{1,2}(?:st|nd|rd|th)?\s+)?'
    r'(?:January|February|March|April|May|June|July|August|September|October|'
    r'November|December)\s+\d{1,2}?,?\s*\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{4})',
    re.IGNORECASE,
)

_ROLE_RE = re.compile(
    r'\b(Chief Information Security Officer|Chief Compliance Officer|Compliance Officer|'
    r'Designated Director|Principal Officer|Chief Risk Officer|Chief Executive Officer|'
    r'Risk Management Committee|Audit Committee|Board of Directors|the Board|'
    r'Investor Grievance Redressal Officer|Head of Operations|Managing Director|'
    r'senior management|Designated Authority)\b',
    re.IGNORECASE,
)

_ENTITY_RE = re.compile(
    r'\b(stock broker(?:s)?|trading member(?:s)?|clearing member(?:s)?|'
    r'depository participant(?:s)?|depositor(?:y|ies)|listed entit(?:y|ies)|'
    r'listed compan(?:y|ies)|investment adviser(?:s)?|research analyst(?:s)?|'
    r'portfolio manager(?:s)?|asset management compan(?:y|ies)|mutual fund(?:s)?|'
    r'registrar to an issue and share transfer agent(?:s)?|RTAs?|'
    r'share transfer agent(?:s)?|intermediar(?:y|ies))\b',
    re.IGNORECASE,
)

# entity phrase → intermediary type used across the app
_ENTITY_TO_TYPE = [
    (r'stock broker|trading member|clearing member', "stockbroker"),
    (r'depositor', "depository"),
    (r'listed', "listed_company"),
    (r'investment adviser|research analyst', "investment_adviser"),
    (r'portfolio manager|asset management|mutual fund|fiduciar', "fiduciary"),
    (r'registrar to an issue|share transfer agent|\brta\b', "rta"),
]

_ACTION_RE = re.compile(
    r'\b(?:shall|must|should|is required to|are required to|shall not|may not)\s+'
    r'((?:not\s+)?[a-z][^.;:]{5,120})',
    re.IGNORECASE,
)

_MANDATORY_TERMS = [
    "shall not", "shall", "must", "required to", "obliged", "mandatory",
    "ensure", "maintain", "no ", "prohibited",
]

# Evidence heuristics: trigger phrase → artefacts a compliance team would file.
_EVIDENCE_RULES: List[Tuple[str, List[str]]] = [
    (r'polic(y|ies)', ["Board-approved policy document", "Board minutes recording approval"]),
    (r'\bboard\b|committee', ["Minutes of the meeting", "Agenda note placed before the body"]),
    (r'report|submit|intimate|file ', ["Copy of the submitted report", "Acknowledgement from the recipient"]),
    (r'audit|vapt|penetration', ["Independent audit report", "Management response and closure tracker"]),
    (r'register|record|log|preserve|retain', ["Register/log extract", "Retention policy reference"]),
    (r'disclose|website|display', ["Screenshot of the disclosure", "Publication timestamp"]),
    (r'appoint|designate', ["Appointment/designation letter", "Intimation to the regulator"]),
    (r'train|awareness|programme', ["Attendance records", "Training material"]),
    (r'verif|kyc|due diligence|screen', ["Verification record", "Screening tool output"]),
    (r'reconcil', ["Reconciliation statement", "Discrepancy closure record"]),
    (r'margin|collateral|fund', ["Ledger extract", "Daily margin/fund statement"]),
    (r'encrypt|authenticat|access control', ["System configuration evidence", "Access review report"]),
    (r'test|drill|simulat', ["Test/drill report", "Observations and remediation log"]),
    (r'complaint|grievance|scores', ["Complaint register extract", "Action Taken Report"]),
    (r'review', ["Signed review note", "Evidence of periodic review"]),
]

_STOPWORDS = {
    "shall", "the", "and", "of", "to", "in", "for", "a", "an", "by", "with", "on",
    "such", "any", "its", "that", "this", "as", "or", "be", "is", "are", "from",
    "all", "every", "not", "which", "may", "at", "it", "has", "have", "under",
    "within", "shall", "shall", "their", "there", "been", "than", "into", "each",
}


def _find_deadline(sentence: str) -> Tuple[Optional[str], str]:
    """Return (deadline_string, deadline_type) using surface patterns only."""
    m = _RELATIVE_RE.search(sentence)
    if m:
        return f"within {m.group(1)} {m.group(2)}".lower(), "relative"
    m = _DATE_RE.search(sentence)
    if m:
        return m.group(1).strip(), "fixed"
    m = _FREQ_RE.search(sentence)
    if m:
        return m.group(1).lower(), "recurring"
    return None, "not_specified"


def _find_responsible(sentence: str, fallback: str = "Compliance Officer") -> str:
    m = _ROLE_RE.search(sentence)
    if m:
        role = m.group(1)
        return "Board of Directors" if role.lower() == "the board" else role.title() \
            if role.islower() else role
    m = _ENTITY_RE.search(sentence)
    if m:
        return f"{m.group(1).title()} — {fallback}"
    return fallback


def _find_action(sentence: str) -> str:
    m = _ACTION_RE.search(sentence)
    if not m:
        return sentence[:160].strip()
    action = " ".join(m.group(1).split())
    action = re.sub(r'\s*\b(and|or)\s*$', '', action).strip(" ,;")
    return action[:1].upper() + action[1:]


def _make_title(action: str, sentence: str) -> str:
    base = action or sentence
    words = base.split()
    title = " ".join(words[:11])
    if len(words) > 11:
        title += "…"
    return title[:1].upper() + title[1:]


def _intermediaries_from_text(sentence: str) -> List[str]:
    found = []
    low = sentence.lower()
    for pattern, itype in _ENTITY_TO_TYPE:
        if re.search(pattern, low):
            found.append(itype)
    return sorted(set(found))


def _evidence_for(sentence: str) -> List[str]:
    low = sentence.lower()
    out: List[str] = []
    for pattern, artefacts in _EVIDENCE_RULES:
        if re.search(pattern, low):
            for a in artefacts:
                if a not in out:
                    out.append(a)
        if len(out) >= 4:
            break
    return out[:4] or ["Documentary evidence of compliance", "Sign-off by the responsible officer"]


def _keywords(sentence: str, limit: int = 6) -> List[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z-]{3,}", sentence.lower())
    seen, out = set(), []
    for w in words:
        if w in _STOPWORDS or w in seen:
            continue
        seen.add(w)
        out.append(w)
        if len(out) >= limit:
            break
    return out


def _mandatory_terms(sentence: str) -> List[str]:
    low = sentence.lower()
    return [t.strip() for t in _MANDATORY_TERMS if t in low][:4]


# ── Sentence walk with section context ───────────────────────────────────────

_SECTION_HEADING_RE = re.compile(r'^\s*(?:\d+(?:\.\d+)*\.?|[IVX]+\.)\s+\S')
_NOT_A_SECTION = re.compile(
    r'^(?:to,?|madam|sir|dear|all\s|yours\s|general manager|encl|copy to|'
    r'securities and exchange board|annexure|appendix)', re.IGNORECASE)


def _is_section_heading(line: str) -> bool:
    if _NOT_A_SECTION.match(line.strip()):
        return False
    if _SECTION_HEADING_RE.match(line):
        return True
    # Unnumbered ALL-CAPS headings are also common in SEBI drafting.
    return line.isupper() and 2 <= len(line.split()) <= 10


def iter_units(text: str) -> Iterable[Dict]:
    """
    Yield {sentence, section, clause_number, order} preserving document structure,
    so every extracted obligation can point back at a real clause reference.
    """
    section = "General"
    order = 0
    for kind, block in segment_blocks(text):
        if kind == "heading":
            # Only a real section heading changes the section. Addressee lines and
            # salutations also parse as short title-case lines, and letting them
            # through would mislabel every clause reference that follows.
            if _is_section_heading(block):
                section = block.strip()
            continue
        clause_no, body = strip_clause_number(block)
        for sent in split_sentences(body):
            order += 1
            yield {
                "sentence": sent,
                "section": section,
                "clause_number": clause_no,
                "order": order,
            }


# ── Public API ───────────────────────────────────────────────────────────────

def extract_obligations_ml(
    text: str,
    circular_id: str,
    circular_title: str,
    intermediary_types: Optional[List[str]] = None,
    threshold: float = 0.55,
    model: Optional[RegGraphModel] = None,
    explain: bool = True,
) -> Tuple[List[Obligation], Dict]:
    """
    Extract obligations with the trained model.

    Returns (obligations, diagnostics). Diagnostics carry the sentence-level
    scores so the UI can show what was considered and rejected, not just what
    survived — the part that makes the output auditable.
    """
    model = model or RegGraphModel.get()
    units = [u for u in iter_units(text) if not is_boilerplate(u["sentence"])]
    if not units:
        return [], {"sentences_considered": 0, "obligations_found": 0, "rejected": []}

    sentences = [u["sentence"] for u in units]
    scored = model.classify_sentences(sentences, threshold=threshold)

    obligations: List[Obligation] = []
    rejected: List[Dict] = []

    for idx, (unit, pred) in enumerate(zip(units, scored)):
        sentence = unit["sentence"]
        if not pred["is_obligation"]:
            if pred["obligation_probability"] >= 0.30:
                rejected.append({
                    "text": sentence[:200],
                    "probability": pred["obligation_probability"],
                    "section": unit["section"],
                })
            continue

        deadline, deadline_type = _find_deadline(sentence)
        # Trust the surface pattern when it finds one; fall back to the model head.
        if deadline is None and pred.get("deadline_type") in ("recurring", "relative", "fixed"):
            deadline_type = pred["deadline_type"]

        severity, severity_basis = assess_severity(
            sentence,
            deadline_type=deadline_type,
            model_severity=pred.get("severity"),
            model_confidence=pred.get("severity_confidence", 0.0),
        )

        action = _find_action(sentence)
        text_itypes = _intermediaries_from_text(sentence)
        model_itypes = pred.get("intermediary_types", [])
        applies = text_itypes or model_itypes or (intermediary_types or ["stockbroker"])
        if intermediary_types:
            # Keep the user's selection authoritative, but retain anything the
            # clause names explicitly so the graph doesn't lose applicability.
            applies = sorted(set(applies) & set(intermediary_types)) or intermediary_types

        evidence = _evidence_for(sentence)
        rationale_bits = model.explain(sentence, "obligation_clf", top_k=5) if explain else []
        rationale = (
            f"Classified as an obligation with probability {pred['obligation_probability']:.2f} "
            f"by the local model (section: {unit['section']}). "
            + ("Strongest signals: "
               + ", ".join(f"'{b['feature']}'" for b in rationale_bits if b["direction"] == "supports")
               + ". " if rationale_bits else "")
            + f"Severity {severity} — {severity_basis}."
        )

        clause_ref = unit["clause_number"] or ""
        clause_reference = (
            f"Clause {clause_ref} — {unit['section']}" if clause_ref
            else f"{circular_title or circular_id} — {unit['section']}"
        )

        obligations.append(Obligation(
            obligation_id=f"{circular_id}_obl_{len(obligations)}",
            circular_id=circular_id,
            clause_reference=f"{clause_reference}: \"{sentence[:180]}\"",
            title=_make_title(action, sentence),
            description=sentence,
            responsible_party=_find_responsible(sentence),
            required_action=action,
            deadline=deadline,
            deadline_type=deadline_type,
            intermediary_types=applies,
            conditions={},
            evidence_requirements=evidence,
            evidence_status=EvidenceStatus.MISSING,
            keywords=_keywords(sentence),
            severity=severity,
            status=ObligationStatus.ACTIVE,
            extraction_rationale=rationale,
            confidence_score=round(float(pred["obligation_probability"]), 3),
            mandatory_keywords=_mandatory_terms(sentence),
            evidence_checklist=[
                ChecklistItem(item_id=f"chk_{j}", label=req, completed=False)
                for j, req in enumerate(evidence)
            ],
        ))

    diagnostics = {
        "sentences_considered": len(sentences),
        "obligations_found": len(obligations),
        "threshold": threshold,
        "mean_confidence": round(
            sum(o.confidence_score for o in obligations) / len(obligations), 3
        ) if obligations else 0.0,
        "rejected": sorted(rejected, key=lambda r: -r["probability"])[:15],
        "model_version": model.version,
    }
    return obligations, diagnostics


def merge_obligation_sets(
    ml_obligations: List[Obligation],
    llm_obligations: List[Obligation],
    circular_id: str,
    match_threshold: float = 0.55,
) -> Tuple[List[Obligation], Dict]:
    """
    Combine the local model's extractions with the LLM's.

    Where both found the same clause, the LLM's richer wording is kept but the
    local model's clause reference, confidence and rationale are preserved — those
    are traceable to the document, the LLM's are not. Anything either side found
    alone is kept: for compliance, a missed obligation costs more than a duplicate
    an analyst can dismiss.
    """
    if not llm_obligations:
        return ml_obligations, {"strategy": "ml_only", "matched": 0,
                                "ml_only": len(ml_obligations), "llm_only": 0}
    if not ml_obligations:
        return llm_obligations, {"strategy": "llm_only", "matched": 0,
                                 "ml_only": 0, "llm_only": len(llm_obligations)}

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except ImportError:                                            # pragma: no cover
        return ml_obligations + llm_obligations, {"strategy": "concat"}

    ml_texts = [o.description for o in ml_obligations]
    llm_texts = [o.description for o in llm_obligations]
    try:
        vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2)).fit(ml_texts + llm_texts)
        sim = cosine_similarity(vec.transform(llm_texts), vec.transform(ml_texts))
    except ValueError:
        return ml_obligations + llm_obligations, {"strategy": "concat"}

    merged: List[Obligation] = list(ml_obligations)
    used_ml: set = set()
    matched = 0
    llm_only = 0

    for i, llm_obl in enumerate(llm_obligations):
        j = int(sim[i].argmax())
        if sim[i, j] >= match_threshold and j not in used_ml:
            used_ml.add(j)
            matched += 1
            base = merged[j]
            # LLM wins on prose fields when it actually said something.
            if llm_obl.title:
                base.title = llm_obl.title
            if llm_obl.required_action:
                base.required_action = llm_obl.required_action
            if llm_obl.responsible_party:
                base.responsible_party = llm_obl.responsible_party
            if llm_obl.deadline and not base.deadline:
                base.deadline = llm_obl.deadline
                base.deadline_type = llm_obl.deadline_type or base.deadline_type
            if llm_obl.evidence_requirements:
                base.evidence_requirements = sorted(
                    set(base.evidence_requirements) | set(llm_obl.evidence_requirements)
                )[:6]
                base.evidence_checklist = [
                    ChecklistItem(item_id=f"chk_{k}", label=req, completed=False)
                    for k, req in enumerate(base.evidence_requirements)
                ]
            if llm_obl.keywords:
                base.keywords = sorted(set(base.keywords) | set(llm_obl.keywords))[:8]
            # Agreement between two independent extractors is real evidence.
            base.confidence_score = round(min(1.0, base.confidence_score + 0.05), 3)
            base.extraction_rationale = (
                (base.extraction_rationale or "")
                + " Confirmed independently by the LLM extraction pass."
            )
        else:
            llm_only += 1
            merged.append(llm_obl)

    for n, obl in enumerate(merged):
        obl.obligation_id = f"{circular_id}_obl_{n}"

    return merged, {
        "strategy": "hybrid",
        "matched": matched,
        "ml_only": len(ml_obligations) - matched,
        "llm_only": llm_only,
        "total": len(merged),
    }


def link_by_similarity(obligations: List[Obligation], top_k: int = 2,
                       min_sim: float = 0.25) -> List[Obligation]:
    """
    Connect obligations that share subject matter, so the graph has edges even
    when the LLM relationship pass is unavailable.

    Uses TF-IDF cosine similarity over the clause text — cheap, deterministic and
    explainable, unlike an LLM guess at dependencies.
    """
    if len(obligations) < 2:
        return obligations
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except ImportError:  # pragma: no cover
        return obligations

    texts = [f"{o.title} {o.description}" for o in obligations]
    try:
        M = TfidfVectorizer(stop_words="english", ngram_range=(1, 2)).fit_transform(texts)
    except ValueError:
        return obligations
    sim = cosine_similarity(M)

    for i, obl in enumerate(obligations):
        row = [(j, sim[i, j]) for j in range(len(obligations)) if j != i and sim[i, j] >= min_sim]
        row.sort(key=lambda kv: -kv[1])
        obl.related_obligations = [obligations[j].obligation_id for j, _ in row[:top_k]]
    return obligations
