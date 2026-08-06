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




class EvidenceRequirementDetail(BaseModel):
    requirement: str
    satisfied: bool
    score: float
    reasoning: str


class EvidenceMatchResultV2(BaseModel):
    obligation_id: str
    obligation_title: str
    match_score: float
    evidence_status: str
    matched_requirements: List[str]
    unmatched_requirements: List[str]
    per_requirement: List[EvidenceRequirementDetail]
    overall_reasoning: str
    method: str  # "llm" or "keyword_fallback"


@router.post("/upload")
async def upload_evidence(
    file: UploadFile = File(...),
    obligation_id: str = Form(...),
    uploaded_by: str = Form(default="compliance_officer"),
):
    """
    Upload an evidence document (PDF/TXT) and semantically match it against an
    obligation's evidence_requirements using the LLM Evidence Agent.
    Falls back to keyword matching if LLM is unavailable.
    """
    from app.agents.evidence_agent import match_evidence

    obligation = orchestrator.graph.get_obligation(obligation_id)
    if not obligation:
        raise HTTPException(status_code=404, detail=f"Obligation {obligation_id} not found")

    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1", errors="ignore")

    # ── Semantic / LLM evidence matching ────────────────────────────────────
    match_result = match_evidence(
        document_text=text,
        obligation_title=obligation.title,
        obligation_description=obligation.description,
        evidence_requirements=obligation.evidence_requirements or [],
        clause_reference=obligation.clause_reference,
    )

    score    = match_result["overall_score"]
    matched  = match_result["matched"]
    unmatched = match_result["unmatched"]
    per_req  = match_result["per_requirement"]
    reasoning = match_result["overall_reasoning"]
    method   = match_result["method"]

    # Determine new evidence status
    status_map = {"green": EvidenceStatus.COMPLETE, "yellow": EvidenceStatus.PARTIAL, "red": EvidenceStatus.MISSING}
    new_status = status_map.get(match_result["evidence_status"], EvidenceStatus.MISSING)

    # Persist evidence file
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    save_path = os.path.join(EVIDENCE_DIR, f"{obligation_id}_{file.filename}")
    with open(save_path, "wb") as f:
        f.write(content)

    # Update obligation status and notes in graph
    node = orchestrator.graph.graph.nodes.get(obligation_id, {})
    if "obligation" in node:
        node["obligation"].evidence_status = new_status
        node["obligation"].evidence_notes = (
            f"Evidence uploaded: {file.filename} | score={score:.2f} | "
            f"method={method} | matched={len(matched)}/{len(matched)+len(unmatched)} | "
            f"{reasoning[:200]}"
        )

    # Update evidence index — store full reasoning for UI display
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
        "per_requirement": per_req,
        "overall_reasoning": reasoning,
        "method": method,
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
            "method": method,
        },
        actor=uploaded_by,
    )

    orchestrator.graph.save()

    return EvidenceMatchResultV2(
        obligation_id=obligation_id,
        obligation_title=obligation.title,
        match_score=score,
        evidence_status=new_status.value,
        matched_requirements=matched,
        unmatched_requirements=unmatched,
        per_requirement=[EvidenceRequirementDetail(**r) for r in per_req],
        overall_reasoning=reasoning,
        method=method,
    )


class ChecklistUpdateRequest(BaseModel):
    item_id: str
    completed: bool
    completed_by: Optional[str] = "compliance_officer"
    notes: Optional[str] = None


@router.get("/checklist/{obligation_id}")
async def get_evidence_checklist(obligation_id: str):
    """Get the evidence checklist for an obligation with progress."""
    obl = orchestrator.graph.get_obligation(obligation_id)
    if not obl:
        raise HTTPException(status_code=404, detail=f"Obligation {obligation_id} not found")
    from app.models.obligation import ChecklistItem
    if not obl.evidence_checklist:
        obl.evidence_checklist = [
            ChecklistItem(item_id=f"chk_{i}", label=req)
            for i, req in enumerate(obl.evidence_requirements)
        ]
        orchestrator.graph.save()
    checklist = obl.evidence_checklist
    total = len(checklist)
    completed = sum(1 for c in checklist if c.completed)
    return {"obligation_id": obligation_id, "title": obl.title,
            "progress": f"{completed}/{total}",
            "completion_pct": round((completed / total * 100) if total > 0 else 0, 1),
            "checklist": [c.model_dump() for c in checklist]}


@router.patch("/checklist/{obligation_id}")
async def update_checklist_item(obligation_id: str, update: ChecklistUpdateRequest):
    """Mark a checklist item as complete/incomplete."""
    obl = orchestrator.graph.get_obligation(obligation_id)
    if not obl:
        raise HTTPException(status_code=404, detail=f"Obligation {obligation_id} not found")
    item = next((c for c in obl.evidence_checklist if c.item_id == update.item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail=f"Checklist item {update.item_id} not found")
    item.completed = update.completed
    item.completed_by = update.completed_by
    item.completed_at = datetime.now() if update.completed else None
    item.notes = update.notes
    total = len(obl.evidence_checklist)
    done = sum(1 for c in obl.evidence_checklist if c.completed)
    if done == total and total > 0:
        obl.evidence_status = EvidenceStatus.COMPLETE
    elif done > 0:
        obl.evidence_status = EvidenceStatus.PARTIAL
    else:
        obl.evidence_status = EvidenceStatus.MISSING
    orchestrator.graph.save()
    return {"obligation_id": obligation_id, "item_id": update.item_id,
            "completed": update.completed, "evidence_status": obl.evidence_status.value,
            "progress": f"{done}/{total}"}


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
