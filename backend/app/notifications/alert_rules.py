"""
Alert Rules Engine — Track 4
Scans the obligation graph and urgency queue to identify conditions that
warrant a compliance notification.

Three rule types:
  OVERDUE    — obligation deadline has passed, evidence not complete
  DUE_SOON   — obligation due within NOTIFY_DUE_SOON_DAYS, evidence not complete
  NEW_HIGH   — HIGH severity obligation added within the last 24 hours
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from app.config import get_settings

logger = logging.getLogger(__name__)

# Severity ordering for filtering
_SEV_ORDER = {"low": 0, "medium": 1, "high": 2}


def _sev_ok(obligation_severity: str, min_severity: str) -> bool:
    """Return True if obligation_severity meets or exceeds min_severity threshold."""
    return _SEV_ORDER.get(obligation_severity, 0) >= _SEV_ORDER.get(min_severity, 1)


def scan_alerts(
    graph,                         # ObligationGraph instance
    urgency_queue: List[Dict],
    due_soon_days: Optional[int] = None,
    min_severity: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Scan obligations and return a structured alert payload.

    Returns:
        {
            "overdue":   [alert_item, ...],
            "due_soon":  [alert_item, ...],
            "new_high":  [alert_item, ...],
            "total_alerts": int,
            "scanned_at": ISO timestamp,
            "has_critical": bool,
        }
    """
    settings = get_settings()
    due_soon_days = due_soon_days if due_soon_days is not None else settings.NOTIFY_DUE_SOON_DAYS
    min_severity  = min_severity  if min_severity  is not None else settings.NOTIFY_MIN_SEVERITY

    now = datetime.now()
    cutoff_new = now - timedelta(hours=24)

    overdue_alerts:  List[Dict] = []
    due_soon_alerts: List[Dict] = []
    new_high_alerts: List[Dict] = []

    for item in urgency_queue:
        sev = item.get("severity", "low")
        ev  = item.get("evidence_status", "red")

        # Skip if severity below threshold
        if not _sev_ok(sev, min_severity):
            continue

        # Skip if evidence already complete
        if ev == "green":
            continue

        days = item.get("days_remaining")
        overdue = item.get("overdue", False)

        alert = {
            "obligation_id":   item["obligation_id"],
            "title":           item["title"],
            "severity":        sev,
            "evidence_status": ev,
            "deadline":        item.get("deadline") or "No deadline",
            "days_remaining":  days,
            "responsible_party": item.get("responsible_party", "—"),
            "intermediary_types": item.get("intermediary_types", []),
            "risk_score":      item.get("risk_score", 0),
        }

        # ── Rule 1: OVERDUE ──────────────────────────────────────────────
        if overdue:
            alert["rule"]        = "OVERDUE"
            alert["alert_label"] = f"⚠ OVERDUE by {abs(days)} days"
            overdue_alerts.append(alert)

        # ── Rule 2: DUE SOON ─────────────────────────────────────────────
        elif days is not None and 0 <= days <= due_soon_days:
            alert["rule"]        = "DUE_SOON"
            alert["alert_label"] = f"🔔 Due in {days} days"
            due_soon_alerts.append(alert)

    # ── Rule 3: NEW HIGH obligations (added in last 24h) ─────────────────
    all_obligations = graph.get_all_obligations()
    for obl in all_obligations:
        if obl.severity != "high":
            continue
        created = obl.created_at
        if created and created >= cutoff_new:
            if _sev_ok(obl.severity, min_severity):
                new_high_alerts.append({
                    "obligation_id":    obl.obligation_id,
                    "title":            obl.title,
                    "severity":         obl.severity,
                    "evidence_status":  obl.evidence_status.value,
                    "deadline":         obl.deadline or "Not specified",
                    "responsible_party": obl.responsible_party,
                    "intermediary_types": obl.intermediary_types,
                    "circular_id":      obl.circular_id,
                    "created_at":       created.isoformat(),
                    "rule":             "NEW_HIGH",
                    "alert_label":      "🆕 New HIGH obligation",
                })

    total = len(overdue_alerts) + len(due_soon_alerts) + len(new_high_alerts)
    has_critical = bool(overdue_alerts) or any(
        a["severity"] == "high" for a in due_soon_alerts + new_high_alerts
    )

    logger.info(
        f"Alert scan complete: {len(overdue_alerts)} overdue, "
        f"{len(due_soon_alerts)} due soon, {len(new_high_alerts)} new high — total {total}"
    )

    return {
        "overdue":      overdue_alerts,
        "due_soon":     due_soon_alerts,
        "new_high":     new_high_alerts,
        "total_alerts": total,
        "scanned_at":   now.isoformat(),
        "has_critical": has_critical,
        "parameters": {
            "due_soon_days": due_soon_days,
            "min_severity":  min_severity,
        },
    }
