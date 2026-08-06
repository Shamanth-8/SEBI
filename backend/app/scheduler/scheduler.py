"""
APScheduler — SEBI Circular Auto-Fetch Job
Runs sebi_fetcher.run_fetch() every 6 hours automatically.
Also exposed via /api/v1/fetcher/run for manual trigger.
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler = None


def _fetch_job(orchestrator):
    """The actual job function run by APScheduler."""
    from app.scheduler.sebi_fetcher import run_fetch
    logger.info("⏰ Scheduled SEBI fetch starting...")
    try:
        result = run_fetch(orchestrator, max_new=5)
        ingested = len(result.get("ingested", []))
        errors   = len(result.get("errors", []))
        logger.info(f"⏰ Scheduled fetch complete — ingested={ingested} errors={errors}")
    except Exception as e:
        logger.error(f"⏰ Scheduled fetch failed: {e}")


def start_scheduler(orchestrator) -> BackgroundScheduler:
    """
    Start the background scheduler.
    Call this once from FastAPI startup event.
    """
    global _scheduler

    if _scheduler and _scheduler.running:
        logger.warning("Scheduler already running — skipping start.")
        return _scheduler

    _scheduler = BackgroundScheduler(
        job_defaults={"coalesce": True, "max_instances": 1},
        timezone="Asia/Kolkata",
    )

    _scheduler.add_job(
        func=_fetch_job,
        trigger=IntervalTrigger(hours=6),
        args=[orchestrator],
        id="sebi_auto_fetch",
        name="SEBI Circular Auto-Fetch",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("✅ SEBI auto-fetch scheduler started (interval: every 6 hours)")
    return _scheduler


def stop_scheduler():
    """Gracefully stop the scheduler. Call from FastAPI shutdown event."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")


def get_scheduler_status() -> dict:
    """Return current scheduler state for the /status endpoint."""
    global _scheduler
    if not _scheduler:
        return {"running": False, "jobs": []}

    jobs = []
    for job in _scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append({
            "id":           job.id,
            "name":         job.name,
            "next_run":     next_run.isoformat() if next_run else None,
            "trigger":      str(job.trigger),
        })

    return {
        "running": _scheduler.running,
        "jobs":    jobs,
    }
