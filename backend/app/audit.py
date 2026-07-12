"""
Audit logging system for RegGraph.
Every pipeline action is timestamped and persisted to data/audit_log.json.
"""
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

AUDIT_LOG_PATH = os.getenv("AUDIT_LOG_PATH", "./data/audit_log.json")


def _load() -> list:
    os.makedirs(os.path.dirname(AUDIT_LOG_PATH), exist_ok=True)
    if os.path.exists(AUDIT_LOG_PATH):
        try:
            with open(AUDIT_LOG_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def _save(entries: list) -> None:
    os.makedirs(os.path.dirname(AUDIT_LOG_PATH), exist_ok=True)
    with open(AUDIT_LOG_PATH, "w") as f:
        json.dump(entries, f, indent=2, default=str)


def log_event(
    event_type: str,
    circular_id: str,
    details: Dict[str, Any],
    actor: str = "system",
    status: str = "success",
    error: Optional[str] = None,
) -> Dict:
    """
    Append one audit entry.

    event_type values used in pipeline:
      CIRCULAR_UPLOAD_STARTED, EXTRACTION_COMPLETE, DIFF_COMPLETE,
      IMPACT_PROPAGATION_COMPLETE, COMPLIANCE_MAPPING_COMPLETE,
      CIRCULAR_PROCESSING_COMPLETE, CIRCULAR_PROCESSING_FAILED,
      EVIDENCE_UPLOADED, OBLIGATION_STATUS_CHANGED
    """
    entry = {
        "timestamp": datetime.now().isoformat(),
        "event_type": event_type,
        "circular_id": circular_id,
        "actor": actor,
        "status": status,
        "details": details,
    }
    if error:
        entry["error"] = error

    entries = _load()
    entries.append(entry)
    _save(entries)

    logger.info(f"[AUDIT] {event_type} | circular={circular_id} | status={status}")
    return entry


def get_audit_trail(circular_id: Optional[str] = None) -> List[Dict]:
    entries = _load()
    if circular_id:
        return [e for e in entries if e.get("circular_id") == circular_id]
    return entries


def get_summary() -> Dict:
    entries = _load()
    circulars_processed = {
        e["circular_id"]
        for e in entries
        if e["event_type"] == "CIRCULAR_PROCESSING_COMPLETE"
    }
    failures = [e for e in entries if e.get("status") == "failure"]
    return {
        "total_events": len(entries),
        "circulars_processed": len(circulars_processed),
        "failures": len(failures),
        "last_event": entries[-1]["timestamp"] if entries else None,
    }
