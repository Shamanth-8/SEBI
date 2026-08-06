"""
Notifier — Track 4
Sends compliance alert digests via:
  - SMTP email (HTML formatted digest)
  - Slack / generic webhook (JSON POST)

Call send_alerts(alert_payload) with the output of alert_rules.scan_alerts().
"""
import json
import logging
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, List, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


# ─── Public entry point ───────────────────────────────────────────────────────

def send_alerts(
    alert_payload: Dict[str, Any],
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Send alert digest to all configured channels.

    Args:
        alert_payload: Output of alert_rules.scan_alerts()
        dry_run:       If True, build messages but don't actually send

    Returns:
        {
            "email":   {"sent": bool, "error": str|None},
            "webhook": {"sent": bool, "error": str|None},
            "dry_run": bool,
            "summary": str,
        }
    """
    settings = get_settings()

    if alert_payload.get("total_alerts", 0) == 0:
        logger.info("No alerts to send.")
        return {"email": {"sent": False}, "webhook": {"sent": False},
                "dry_run": dry_run, "summary": "No alerts — nothing sent."}

    email_result   = {"sent": False, "error": None}
    webhook_result = {"sent": False, "error": None}

    # ── Email ────────────────────────────────────────────────────────────────
    if settings.NOTIFY_EMAIL_TO and settings.SMTP_USER:
        html_body = _build_email_html(alert_payload)
        if dry_run:
            logger.info("[DRY RUN] Email digest ready — not sending.")
            email_result = {"sent": False, "dry_run": True, "preview": html_body[:500]}
        else:
            try:
                _send_email(
                    to=settings.NOTIFY_EMAIL_TO,
                    subject=_email_subject(alert_payload),
                    html_body=html_body,
                )
                email_result = {"sent": True, "to": settings.NOTIFY_EMAIL_TO}
                logger.info(f"Email digest sent to {settings.NOTIFY_EMAIL_TO}")
            except Exception as e:
                email_result = {"sent": False, "error": str(e)}
                logger.error(f"Email send failed: {e}")
    else:
        email_result = {"sent": False, "error": "SMTP not configured (NOTIFY_EMAIL_TO or SMTP_USER missing)"}

    # ── Webhook / Slack ──────────────────────────────────────────────────────
    if settings.NOTIFY_WEBHOOK_URL:
        payload = _build_webhook_payload(alert_payload)
        if dry_run:
            logger.info("[DRY RUN] Webhook payload ready — not sending.")
            webhook_result = {"sent": False, "dry_run": True, "payload": payload}
        else:
            try:
                _post_webhook(settings.NOTIFY_WEBHOOK_URL, payload)
                webhook_result = {"sent": True, "url": settings.NOTIFY_WEBHOOK_URL}
                logger.info(f"Webhook notification sent to {settings.NOTIFY_WEBHOOK_URL}")
            except Exception as e:
                webhook_result = {"sent": False, "error": str(e)}
                logger.error(f"Webhook send failed: {e}")
    else:
        webhook_result = {"sent": False, "error": "Webhook not configured (NOTIFY_WEBHOOK_URL missing)"}

    total = alert_payload.get("total_alerts", 0)
    summary = (
        f"Sent alerts for {total} item(s): "
        f"{len(alert_payload.get('overdue', []))} overdue, "
        f"{len(alert_payload.get('due_soon', []))} due soon, "
        f"{len(alert_payload.get('new_high', []))} new HIGH."
    )

    return {
        "email":   email_result,
        "webhook": webhook_result,
        "dry_run": dry_run,
        "summary": summary,
        "total_alerts": total,
    }


# ─── Email helpers ────────────────────────────────────────────────────────────

def _email_subject(alert_payload: Dict) -> str:
    n = alert_payload.get("total_alerts", 0)
    has_critical = alert_payload.get("has_critical", False)
    prefix = "🚨 CRITICAL" if has_critical else "🔔"
    return f"{prefix} RegGraph Compliance Alert — {n} action(s) require attention"


def _build_email_html(alert_payload: Dict) -> str:
    overdue   = alert_payload.get("overdue",   [])
    due_soon  = alert_payload.get("due_soon",  [])
    new_high  = alert_payload.get("new_high",  [])
    scanned   = alert_payload.get("scanned_at", "")[:19]
    total     = alert_payload.get("total_alerts", 0)

    def alert_rows(items: List[Dict], rule_color: str) -> str:
        if not items:
            return "<tr><td colspan='5' style='color:#64748B;font-size:0.85rem;padding:8px'>— None —</td></tr>"
        rows = ""
        for a in items:
            days_txt = (
                f"<b style='color:#EF4444'>{abs(a['days_remaining'])}d overdue</b>"
                if a.get("overdue") or (a.get("days_remaining") is not None and a["days_remaining"] < 0)
                else (f"{a['days_remaining']}d" if a.get("days_remaining") is not None else "—")
            )
            sev_color = {"high": "#EF4444", "medium": "#F59E0B", "low": "#22C55E"}.get(a["severity"], "#94A3B8")
            rows += f"""
            <tr style='border-bottom:1px solid #1E293B'>
              <td style='padding:8px 12px;font-size:0.85rem'>{a['title'][:70]}</td>
              <td style='padding:8px 12px;font-size:0.82rem;color:{sev_color};font-weight:600'>{a['severity'].upper()}</td>
              <td style='padding:8px 12px;font-size:0.82rem'>{a.get('deadline','—')}</td>
              <td style='padding:8px 12px;font-size:0.82rem'>{days_txt}</td>
              <td style='padding:8px 12px;font-size:0.82rem;color:#94A3B8'>{a.get('responsible_party','—')}</td>
            </tr>"""
        return rows

    def section(title: str, color: str, items: List[Dict]) -> str:
        return f"""
        <h3 style='color:{color};margin:24px 0 8px 0;font-size:1rem'>{title} ({len(items)})</h3>
        <table style='width:100%;border-collapse:collapse;background:#131826;border-radius:8px;overflow:hidden'>
          <thead>
            <tr style='background:#1E293B'>
              <th style='padding:8px 12px;text-align:left;font-size:0.75rem;color:#64748B;text-transform:uppercase'>Obligation</th>
              <th style='padding:8px 12px;text-align:left;font-size:0.75rem;color:#64748B;text-transform:uppercase'>Severity</th>
              <th style='padding:8px 12px;text-align:left;font-size:0.75rem;color:#64748B;text-transform:uppercase'>Deadline</th>
              <th style='padding:8px 12px;text-align:left;font-size:0.75rem;color:#64748B;text-transform:uppercase'>Days</th>
              <th style='padding:8px 12px;text-align:left;font-size:0.75rem;color:#64748B;text-transform:uppercase'>Owner</th>
            </tr>
          </thead>
          <tbody>{alert_rows(items, color)}</tbody>
        </table>"""

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset='UTF-8'></head>
<body style='font-family:Inter,system-ui,sans-serif;background:#0B0F19;color:#E2E8F0;padding:32px;max-width:800px;margin:0 auto'>

  <div style='background:#131826;border:1px solid #1E293B;border-radius:12px;padding:24px;margin-bottom:24px'>
    <h1 style='color:#A78BFA;margin:0 0 8px 0;font-size:1.4rem'>🏛 RegGraph Compliance Alert</h1>
    <p style='color:#64748B;margin:0;font-size:0.85rem'>Generated: {scanned} &nbsp;|&nbsp;
      <b style='color:#E2E8F0'>{total}</b> obligation(s) require attention</p>
  </div>

  {'<div style="background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.4);border-radius:8px;padding:12px 16px;margin-bottom:16px"><b style="color:#EF4444">⚠ CRITICAL ITEMS DETECTED</b> — immediate action required.</div>' if alert_payload.get("has_critical") else ""}

  {section("⚠ Overdue Obligations", "#EF4444", overdue)}
  {section("🔔 Due Soon", "#F59E0B", due_soon)}
  {section("🆕 New HIGH Severity", "#A78BFA", new_high)}

  <p style='color:#475569;font-size:0.78rem;margin-top:24px;border-top:1px solid #1E293B;padding-top:12px'>
    This digest was sent by RegGraph — Agentic Compliance System.<br>
    View full dashboard at <a href='http://localhost:8501' style='color:#A78BFA'>http://localhost:8501</a>
  </p>
</body>
</html>"""


def _send_email(to: str, subject: str, html_body: str) -> None:
    settings = get_settings()
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = settings.NOTIFY_EMAIL_FROM or settings.SMTP_USER
    msg["To"]      = to
    msg.attach(MIMEText(html_body, "html"))

    context = ssl.create_default_context()
    if settings.SMTP_USE_TLS:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(msg["From"], to, msg.as_string())
    else:
        with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=context) as server:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(msg["From"], to, msg.as_string())


# ─── Webhook / Slack helpers ──────────────────────────────────────────────────

def _build_webhook_payload(alert_payload: Dict) -> Dict:
    """Build a Slack-compatible Block Kit message (also works as generic JSON)."""
    overdue  = alert_payload.get("overdue",  [])
    due_soon = alert_payload.get("due_soon", [])
    new_high = alert_payload.get("new_high", [])
    total    = alert_payload.get("total_alerts", 0)
    scanned  = alert_payload.get("scanned_at", "")[:19]

    def items_text(items: List[Dict], emoji: str) -> str:
        if not items:
            return "_None_"
        lines = []
        for a in items[:5]:  # max 5 per section in Slack
            days_txt = f"{abs(a['days_remaining'])}d overdue" if a.get("days_remaining", 0) < 0 else f"{a.get('days_remaining','?')}d"
            lines.append(f"• *{a['title'][:60]}* — `{a['severity'].upper()}` — {days_txt} — {a.get('responsible_party','—')}")
        if len(items) > 5:
            lines.append(f"_...and {len(items)-5} more_")
        return "\n".join(lines)

    color = "#EF4444" if alert_payload.get("has_critical") else "#F59E0B"

    # Slack Block Kit format
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"🏛 RegGraph — {total} Compliance Alert(s)"}
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"Scanned at {scanned}"}]
        },
        {"type": "divider"},
    ]

    if overdue:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*⚠ Overdue ({len(overdue)})*\n{items_text(overdue, '⚠')}"}
        })
    if due_soon:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*🔔 Due Soon ({len(due_soon)})*\n{items_text(due_soon, '🔔')}"}
        })
    if new_high:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*🆕 New HIGH Severity ({len(new_high)})*\n{items_text(new_high, '🆕')}"}
        })

    blocks.append({
        "type": "actions",
        "elements": [{
            "type": "button",
            "text": {"type": "plain_text", "text": "Open Dashboard"},
            "url": "http://localhost:8501",
            "style": "primary",
        }]
    })

    return {
        "text": f"RegGraph: {total} compliance alert(s) — {len(overdue)} overdue",
        "attachments": [{"color": color, "blocks": blocks}],
    }


def _post_webhook(url: str, payload: Dict) -> None:
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
