"""
Fetcher API endpoints — Track 3
Exposes manual control and status of the SEBI auto-fetch pipeline.

  POST /api/v1/fetcher/run     — trigger a fetch run immediately
  GET  /api/v1/fetcher/status  — last run status + scheduler state
  GET  /api/v1/fetcher/seen    — list of already-seen circular URLs
  DELETE /api/v1/fetcher/seen/{url_hash} — remove a URL from seen (re-ingest)
"""
import hashlib
import logging
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.scheduler.sebi_fetcher import (
    run_fetch, load_status, _load_seen, _save_seen, SEEN_PATH
)
from app.scheduler.scheduler import get_scheduler_status
from app.api.circulars import orchestrator

router = APIRouter()
logger = logging.getLogger(__name__)

# Track in-progress fetch to prevent concurrent runs
_fetch_running = False


class FetchRequest(BaseModel):
    max_new: int = 5
    dry_run: bool = False
    intermediary_types: Optional[list] = None


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/run")
async def trigger_fetch(req: FetchRequest = FetchRequest()):
    """
    Manually trigger a SEBI circular fetch run.
    Runs synchronously — may take a few minutes depending on max_new.
    Set dry_run=true to detect new circulars without ingesting them.
    """
    global _fetch_running

    if _fetch_running:
        raise HTTPException(status_code=409, detail="A fetch run is already in progress.")

    _fetch_running = True
    try:
        result = run_fetch(
            orchestrator=orchestrator,
            max_new=req.max_new,
            intermediary_types=req.intermediary_types,
            dry_run=req.dry_run,
        )
        return {
            "status":   "complete",
            "ingested": len(result.get("ingested", [])),
            "errors":   len(result.get("errors", [])),
            "dry_run":  req.dry_run,
            "details":  result,
        }
    finally:
        _fetch_running = False


@router.get("/status")
async def fetch_status():
    """
    Return last fetch run status and scheduler state.
    """
    last_run = load_status()
    scheduler = get_scheduler_status()
    seen = _load_seen()

    return {
        "last_run":        last_run,
        "scheduler":       scheduler,
        "seen_count":      len(seen),
        "fetch_in_progress": _fetch_running,
        "seen_file":       str(SEEN_PATH),
    }


@router.get("/seen")
async def list_seen(limit: int = 50, offset: int = 0):
    """
    List all circular URLs that have already been ingested.
    Supports pagination via limit/offset.
    """
    seen = _load_seen()
    items = [
        {
            "url":          url,
            "url_hash":     hashlib.md5(url.encode()).hexdigest()[:8],
            **meta,
        }
        for url, meta in seen.items()
    ]
    # Sort by processed_at descending
    items.sort(key=lambda x: x.get("processed_at", ""), reverse=True)

    return {
        "total":  len(items),
        "offset": offset,
        "limit":  limit,
        "items":  items[offset : offset + limit],
    }


@router.delete("/seen/{url_hash}")
async def remove_from_seen(url_hash: str):
    """
    Remove a circular from the seen registry by its URL hash.
    The next fetch run will re-ingest it.
    Use GET /seen to find url_hash values.
    """
    seen = _load_seen()
    target_url = None
    for url in seen:
        if hashlib.md5(url.encode()).hexdigest()[:8] == url_hash:
            target_url = url
            break

    if not target_url:
        raise HTTPException(status_code=404, detail=f"No seen entry with hash {url_hash}")

    removed = seen.pop(target_url)
    _save_seen(seen)
    return {
        "removed":    target_url,
        "title":      removed.get("title", "—"),
        "message":    "Removed from seen registry. Will be re-ingested on next fetch.",
    }
