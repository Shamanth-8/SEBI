"""
Notification API endpoints — Track 4
Exposes:
  POST /api/v1/notifications/send  — run alert scan + send immediately
  POST /api/v1/notifications/test  — dry-run (build messages, no send)
  GET  /api/v1/notifications/preview — return alert payload without sending
  GET  /api/v1/notifications/config  — show current notification config (no secrets)
"""
import logging
from typing import Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.config import get_settings
from app.notifications.alert_rules import scan_alerts
from app.notifications.notifier import send_alerts
from app.api.circulars import orchestrator  # reuse global orchestrator

router = APIRouter()
logger = logging.getLogger(__name__)


# ─── Request / Response models ────────────────────────────────────────────────

class SendNotificationRequest(BaseModel):
    intermediary_type: Optional[str] = None
    due_soon_days: Optional[int] = None
    min_severity: Optional[str] = None    # low | medium | high
    dry_run: bool = False


class NotificationResult(BaseModel):
    total_alerts: int
    has_critical: bool
    email: dict
    webhook: dict
    dry_run: bool
    summary: str
    alert_counts: dict


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/send")
async def send_notifications(req: SendNotificationRequest = SendNotificationRequest()):
    """
    Scan obligations for alert conditions and send notifications immediately.
    Set dry_run=true to preview without actually sending.
    """
    settings = get_settings()

    urgency_queue = orchestrator.get_urgency_queue(req.intermediary_type)

    alert_payload = scan_alerts(
        graph=orchestrator.graph,
        urgency_queue=urgency_queue,
        due_soon_days=req.due_soon_days,
        min_severity=req.min_severity,
    )

    result = send_alerts(alert_payload, dry_run=req.dry_run)

    return NotificationResult(
        total_alerts=alert_payload["total_alerts"],
        has_critical=alert_payload["has_critical"],
        email=result["email"],
        webhook=result["webhook"],
        dry_run=req.dry_run,
        summary=result["summary"],
        alert_counts={
            "overdue":  len(alert_payload.get("overdue", [])),
            "due_soon": len(alert_payload.get("due_soon", [])),
            "new_high": len(alert_payload.get("new_high", [])),
        },
    )


@router.post("/test")
async def test_notifications(
    intermediary_type: Optional[str] = Query(None),
    due_soon_days: Optional[int] = Query(None),
    min_severity: Optional[str] = Query(None),
):
    """
    Dry-run: scan for alerts and return what would be sent — no emails or webhooks fired.
    Useful for verifying configuration before going live.
    """
    urgency_queue = orchestrator.get_urgency_queue(intermediary_type)

    alert_payload = scan_alerts(
        graph=orchestrator.graph,
        urgency_queue=urgency_queue,
        due_soon_days=due_soon_days,
        min_severity=min_severity,
    )

    result = send_alerts(alert_payload, dry_run=True)

    return {
        "dry_run": True,
        "total_alerts": alert_payload["total_alerts"],
        "has_critical": alert_payload["has_critical"],
        "alert_counts": {
            "overdue":  len(alert_payload.get("overdue", [])),
            "due_soon": len(alert_payload.get("due_soon", [])),
            "new_high": len(alert_payload.get("new_high", [])),
        },
        "alerts": alert_payload,
        "channels": {
            "email":   result["email"],
            "webhook": result["webhook"],
        },
        "message": "Dry-run complete — no messages were sent.",
    }


@router.get("/preview")
async def preview_alerts(
    intermediary_type: Optional[str] = Query(None),
    due_soon_days: Optional[int] = Query(None),
    min_severity: Optional[str] = Query(None),
):
    """
    Return the raw alert payload (what would be sent) without triggering any notification.
    Useful for the dashboard's manual 'Send Now' button preview.
    """
    urgency_queue = orchestrator.get_urgency_queue(intermediary_type)

    alert_payload = scan_alerts(
        graph=orchestrator.graph,
        urgency_queue=urgency_queue,
        due_soon_days=due_soon_days,
        min_severity=min_severity,
    )

    return alert_payload


@router.get("/config")
async def get_notification_config():
    """Return current notification configuration (no secrets exposed)."""
    settings = get_settings()
    return {
        "email_configured":   bool(settings.NOTIFY_EMAIL_TO and settings.SMTP_USER),
        "webhook_configured": bool(settings.NOTIFY_WEBHOOK_URL),
        "notifications_enabled": settings.notifications_enabled,
        "notify_email_to":    settings.NOTIFY_EMAIL_TO or "(not set)",
        "smtp_host":          settings.SMTP_HOST,
        "smtp_port":          settings.SMTP_PORT,
        "webhook_url":        (settings.NOTIFY_WEBHOOK_URL[:40] + "...") if settings.NOTIFY_WEBHOOK_URL else "(not set)",
        "due_soon_days":      settings.NOTIFY_DUE_SOON_DAYS,
        "min_severity":       settings.NOTIFY_MIN_SEVERITY,
    }
