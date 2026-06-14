"""APScheduler configuration for the daily LinkedIn posting job."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.utils.logging import logger
from app.utils.timezone import PHOENIX_TZ

scheduler = AsyncIOScheduler()
_user_id: int | None = None


async def _daily_post_job():
    """Scheduled job that runs the daily pipeline."""
    if _user_id is None:
        logger.warning("Scheduler fired but no user_id configured — skipping")
        return

    logger.info("Scheduled daily job triggered", extra={"user_id": _user_id})

    from app.services.scheduler_service import run_daily_pipeline

    result = await run_daily_pipeline(_user_id)
    logger.info("Scheduled daily job completed", extra={"result_status": result.get("status")})


def configure_scheduler(hour: int = 10, minute: int = 0, user_id: int | None = None):
    """Configure the daily cron job. Call at app startup after first user authenticates."""
    global _user_id
    _user_id = user_id

    trigger = CronTrigger(
        hour=hour,
        minute=minute,
        timezone=PHOENIX_TZ,
    )

    # Remove existing job if any
    existing = scheduler.get_job("daily_linkedin_post")
    if existing:
        scheduler.remove_job("daily_linkedin_post")

    scheduler.add_job(
        _daily_post_job,
        trigger=trigger,
        id="daily_linkedin_post",
        name="Daily LinkedIn Post",
        max_instances=1,
        misfire_grace_time=3600,
        replace_existing=True,
    )
    logger.info(
        "Scheduler configured",
        extra={"hour": hour, "minute": minute, "timezone": "America/Phoenix", "user_id": user_id},
    )


def start_scheduler():
    """Start the scheduler if not already running."""
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started")


def shutdown_scheduler():
    """Gracefully shut down the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler shut down")


def get_scheduler_info() -> dict:
    """Return scheduler status for the UI."""
    job = scheduler.get_job("daily_linkedin_post")
    next_run = None
    if job:
        nrt = getattr(job, "next_run_time", None)
        if nrt:
            next_run = nrt.strftime("%Y-%m-%d %H:%M %Z")

    return {
        "running": scheduler.running,
        "next_run": next_run,
        "job_exists": job is not None,
    }
