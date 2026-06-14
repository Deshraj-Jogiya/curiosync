"""Scheduler status and control routes."""

from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import Settings, get_settings
from app.database import get_db
from app.models.scheduler_run import SchedulerRun
from app.models.token import OAuthToken
from app.services.scheduler_service import run_daily_pipeline, record_scheduler_run
from app.utils.logging import logger
from app.utils.timezone import now_phoenix

router = APIRouter(prefix="/scheduler", tags=["scheduler"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/status")
async def scheduler_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Return scheduler status as an HTMX partial."""
    user_id = request.session.get("user_id")

    # Get scheduler info
    from app.scheduler import get_scheduler_info
    info = get_scheduler_info()

    # Get last success/failure
    last_success = None
    last_failure = None

    result = await db.execute(
        select(SchedulerRun)
        .where(SchedulerRun.status == "success")
        .order_by(SchedulerRun.completed_at.desc())
        .limit(1)
    )
    run = result.scalar_one_or_none()
    if run and run.completed_at:
        last_success = run.completed_at.strftime("%Y-%m-%d %H:%M %Z")

    result = await db.execute(
        select(SchedulerRun)
        .where(SchedulerRun.status == "failed")
        .order_by(SchedulerRun.completed_at.desc())
        .limit(1)
    )
    run = result.scalar_one_or_none()
    if run and run.completed_at:
        last_failure = run.completed_at.strftime("%Y-%m-%d %H:%M %Z")

    # Token status
    token_status = "no_user"
    if user_id:
        result = await db.execute(
            select(OAuthToken)
            .where(OAuthToken.user_id == user_id)
            .order_by(OAuthToken.created_at.desc())
            .limit(1)
        )
        token = result.scalar_one_or_none()
        if not token:
            token_status = "missing"
        elif token.is_expired:
            token_status = "expired"
        elif token.expires_soon:
            token_status = "expires_soon"
        else:
            token_status = "valid"

    return templates.TemplateResponse(
        "partials/scheduler_panel.html",
        {
            "request": request,
            "running": info.get("running", False),
            "next_run": info.get("next_run"),
            "last_success": last_success,
            "last_failure": last_failure,
            "token_status": token_status,
        },
    )


@router.post("/run-now")
async def run_now(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Trigger an immediate pipeline run."""
    user_id = request.session.get("user_id")
    if not user_id:
        return templates.TemplateResponse(
            "partials/toast.html",
            {"request": request, "message": "Not authenticated.", "type": "error"},
        )

    try:
        logger.info("Manual pipeline run triggered by user %s", user_id)
        result = await run_daily_pipeline(user_id, db, settings, run_type="manual")

        status = result.get("status", "unknown")
        if status == "success":
            return templates.TemplateResponse(
                "partials/toast.html",
                {"request": request, "message": "Pipeline completed successfully! Post published.", "type": "success"},
            )
        elif status == "skipped":
            return templates.TemplateResponse(
                "partials/toast.html",
                {"request": request, "message": result.get("reason", "Skipped."), "type": "info"},
            )
        else:
            return templates.TemplateResponse(
                "partials/toast.html",
                {"request": request, "message": f"Pipeline failed: {result.get('error', 'Unknown')}", "type": "error"},
            )

    except Exception as e:
        logger.error("Manual run failed: %s", str(e))
        return templates.TemplateResponse(
            "partials/toast.html",
            {"request": request, "message": f"Run failed: {str(e)}", "type": "error"},
        )
