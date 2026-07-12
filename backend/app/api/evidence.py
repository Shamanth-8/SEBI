"""
Evidence management endpoints.
Allows compliance teams to upload evidence documents and match them to obligations.
"""
import os
import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from app.agents.orchestrator import RegGraphOrchestrator
from app.models.obligation import EvidenceStatus
from app.audit import log_event

router = APIRouter()

# Reuse global orchestrator
from app.api.circulars import orchestrator

EVIDENCE_DIR = os.getenv("EVIDENCE_DIR", "./data/evidence")
EVIDENCE_INDEX_PATH = os.path.join(EVIDENCE_DIR, "index.json")


def _load_index() -> list:
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    if os.path.exists(EVIDENCE_INDEX_PATH):
        with open(EVIDENCE_INDEX_PATH) as f:
            return json.load(f)
    return []


def _save_index(entries: list) -> None:
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    with open(EVIDENCE_INDEX_PATH, "w") as f:
        json.dump(entries, f, indent=2, default=str)


def _keyword_match_score(evidence_text: str, evidence_requirements: List[str]) -> float:
    """
    Simple keyword overlap score between uploaded document text
    and an obligation's evidence_requirements list.
    Returns 0.0 – 1.0.
    """
    if not evidence_requirements:
        return 0.0
    text_lower = evidence_text.lower()
    matched = sum(
        1 for req in evidence_requirements
        if any(word in text_lower for word in req.lower().split())
    )
    return round(matched / len(evidence_requirements), 2)


class EvidenceMatchResult(BaseModel):
    obligation_id: str
    obligation_title: str
    match_score: float          # 0-1
    evidence_status: str        # green / yellow / red
    matched_requirements: List[str]
    unmatched_requirements: List[str]


@router.post("/upload")
async def upload_evidence(
    file: UploadFile = File(...),
    obligation_id: str = Form(...),
    uploaded_by: str = Form(default="compliance_officer"),
):
    """
    Upload an evidence document (PDF/TXT) and match it against an obligation's
    evidence_requirements using keyword matching.
    """
    obligation = orchestrator.graph.get_obligation(obligation_id)
    if not obligation:
        raise HTTPException(status_code=404, detail=f"Obligation {obligation_id} not found")

    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        # PDF or binary — extract readable bytes
        text = content.decode("latin-1", errors="ignore")

    # Match against evidence requirements
    requirements = obligation.evidence_requirements or []
    text_lower = text.lower()
    matched = [r for r in requirements if any(w in text_lower for w in r.lower().split())]
    unmatched = [r for r in requirements if r not in matched]
    score = round(len(matched) / max(len(requirements), 1), 2)

    # Determine new evidence status
    if score >= 0.8:
        new_status = EvidenceStatus.COMPLETE
    elif score >= 0.4:
        new_status = EvidenceStatus.PARTIAL
    else:
        new_status = EvidenceStatus.MISSING

    # Persist evidence file
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    save_path = os.path.join(EVIDENCE_DIR, f"{obligation_id}_{file.filename}")
    with open(save_path, "wb") as f:
        f.write(content)

    # Update obligation status in graph
    node = orchestrator.graph.graph.nodes.get(obligation_id, {})
    if "obligation" in node:
        node["obligation"].evidence_status = new_status
        node["obligation"].evidence_notes = (
            f"Evidence uploaded: {file.filename} | score={score} | "
            f"matched={matched} | unmatched={unmatched}"
        )

    # Update evidence index
    index = _load_index()
    index.append({
        "obligation_id": obligation_id,
        "filename": file.filename,
        "saved_path": save_path,
        "uploaded_by": uploaded_by,
        "uploaded_at": datetime.now().isoformat(),
        "match_score": score,
        "evidence_status": new_status.value,
        "matched_requirements": matched,
        "unmatched_requirements": unmatched,
    })
    _save_index(index)

    # Audit log
    log_event(
        "EVIDENCE_UPLOADED",
        obligation.circular_id,
        {
            "obligation_id": obligation_id,
            "filename": file.filename,
            "match_score": score,
            "evidence_status": new_status.value,
        },
        actor=uploaded_by,
    )

    orchestrator.graph.save()

    return EvidenceMatchResult(
        obligation_id=obligation_id,
        obligation_title=obligation.title,
        match_score=score,
        evidence_status=new_status.value,
        matched_requirements=matched,
        unmatched_requirements=unmatched,
    )


@router.get("/gaps")
async def get_evidence_gaps(circular_id: Optional[str] = None):
    """List all obligations with missing or partial evidence."""
    obligations = orchestrator.graph.get_all_obligations()
    if circular_id:
        obligations = [o for o in obligations if o.circular_id == circular_id]

    gaps = []
    for o in obligations:
        if o.evidence_status != EvidenceStatus.COMPLETE:
            gaps.append({
                "obligation_id": o.obligation_id,
                "title": o.title,
                "circular_id": o.circular_id,
                "evidence_status": o.evidence_status.value,
                "evidence_requirements": o.evidence_requirements,
                "severity": o.severity,
            })

    # Sort: missing red first, then yellow, then by severity
    order = {"red": 0, "yellow": 1, "green": 2}
    gaps.sort(key=lambda g: (order.get(g["evidence_status"], 9), g["severity"] != "high"))
    return {"total_gaps": len(gaps), "gaps": gaps}


@router.get("/list/{obligation_id}")
async def list_evidence(obligation_id: str):
    """List all evidence files uploaded for an obligation."""
    index = _load_index()
    entries = [e for e in index if e["obligation_id"] == obligation_id]
    return {"obligation_id": obligation_id, "count": len(entries), "evidence": entries}
