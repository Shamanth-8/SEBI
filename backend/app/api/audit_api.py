"""
Audit trail and metrics API endpoints.
"""
from typing import Optional
from fastapi import APIRouter
from app.audit import get_audit_trail, get_summary
from app.metrics import get_all_metrics, get_latest_run, format_summary

router = APIRouter()


@router.get("/trail")
async def audit_trail(circular_id: Optional[str] = None):
    """Return full audit trail, optionally filtered by circular_id."""
    entries = get_audit_trail(circular_id)
    return {"count": len(entries), "entries": entries}


@router.get("/summary")
async def audit_summary():
    """Return high-level audit statistics."""
    return get_summary()


@router.get("/metrics")
async def pipeline_metrics(circular_id: Optional[str] = None):
    """Return all pipeline run metrics."""
    if circular_id:
        record = get_latest_run(circular_id)
        return record or {"error": f"No metrics found for {circular_id}"}
    return {"runs": get_all_metrics()}


@router.get("/metrics/latest")
async def latest_metrics():
    """Return the most recent pipeline run metrics."""
    record = get_latest_run()
    if not record:
        return {"error": "No pipeline runs recorded yet"}
    return {"summary": format_summary(record), "data": record}
