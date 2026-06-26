"""Daily pipeline orchestration and scheduler run recording."""

import json
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import async_session
from app.models.draft import Draft
from app.models.user import User
from app.models.scheduler_run import SchedulerRun
from app.services.auth_service import get_valid_token
from app.services.compliance_service import check_compliance, humanize_draft
from app.services.deduplication_service import deduplicate_news
from app.services.linkedin_service import publish_post
from app.services.news_service import fetch_news, save_news_items
from app.services.post_history_service import get_today_post, record_post
from app.services.summarizer_service import generate_draft, generate_monday_project_spotlight
from app.services.github_service import fetch_github_projects
from app.utils.logging import logger
from app.utils.timezone import now_phoenix, today_phoenix


async def run_daily_pipeline(
    user_id: int,
    db: AsyncSession | None = None,
    settings: Settings | None = None,
    run_type: str = "scheduled",
) -> dict:
    """Orchestrate the full daily post pipeline.

    When called from the scheduler (no db/settings args), opens its own session.
    When called from a route (db/settings provided), uses the provided session.
    """
    settings = settings or get_settings()
    own_session = db is None

    if own_session:
        session = async_session()
    else:
        session = db

    date_for = today_phoenix()
    steps: dict[str, str] = {}

    logger.info("Starting daily pipeline", extra={"user_id": user_id, "date_for": str(date_for), "run_type": run_type})

    try:
        # 1. Check duplicate
        existing = await get_today_post(session, user_id, date_for)
        if existing:
            steps["duplicate_check"] = "skipped — already posted today"
            logger.info("Pipeline skipped — already posted today", extra={"user_id": user_id})
            await record_scheduler_run(session, run_type, "skipped", None, steps)
            if own_session:
                await session.commit()
            return {"status": "skipped", "reason": "Already posted today. Duplicate prevented.", "steps": steps}
        steps["duplicate_check"] = "passed"

        # 2. Get valid token
        access_token = await get_valid_token(session, user_id, settings)
        if access_token is None:
            steps["token_check"] = "failed — token expired or missing"
            logger.error("Pipeline failed — no valid token", extra={"user_id": user_id})
            await record_scheduler_run(session, run_type, "failed", "No valid token", steps)
            if own_session:
                await session.commit()
            return {"status": "failed", "error": "LinkedIn token expired. Please re-authorize.", "steps": steps}
        steps["token_check"] = "passed"

        # Fetch news
        news_items = await fetch_news(settings)
        if not news_items:
            steps["fetch_news"] = "failed — no items returned"
            logger.error("Pipeline failed — no news items fetched")
            await record_scheduler_run(session, run_type, "failed", "No news items", steps)
            if own_session:
                await session.commit()
            return {"status": "failed", "error": "No tech news found for today.", "steps": steps}
        steps["fetch_news"] = f"fetched {len(news_items)} items"

        # Deduplicate
        deduped = deduplicate_news(news_items)
        steps["deduplication"] = f"{len(news_items)} -> {len(deduped)} items"

        # Save news to DB
        await save_news_items(session, deduped, date_for)
        steps["save_news"] = f"saved {len(deduped)} items"

        # Generate draft
        draft_text = await generate_draft(deduped, settings)
        steps["generate_draft"] = f"generated ({len(draft_text.split())} words)"

        # Compliance check
        compliance = check_compliance(draft_text, deduped)
        steps["compliance_check"] = "passed" if compliance["passed"] else f"issues: {compliance['issues']}"
        sources_list = [{"title": i["title"], "source_name": i["source_name"]} for i in deduped]
        # 8. Humanize draft
        draft_text = humanize_draft(draft_text)
        steps["humanize"] = "applied"

        # Save draft to DB
        draft = Draft(
            user_id=user_id,
            content=draft_text,
            word_count=len(draft_text.split()),
            char_count=len(draft_text),
            tone="professional",
            sources_json=json.dumps(sources_list),
            compliance_passed=compliance["passed"],
            date_for=date_for,
        )
        session.add(draft)
        await session.flush()

        # 9. Publish to LinkedIn
        user_result = await session.execute(select(User).where(User.id == user_id))
        user = user_result.scalars().first()
        author_urn = f"urn:li:person:{user.linkedin_sub}" if user else ""

        # Generate custom high-engagement graphic on the fly
        image_path = None
        try:
            from app.services.image_service import generate_graphic_metadata, generate_linkedin_image
            metadata = await generate_graphic_metadata(draft_text, settings)
            subtitle = "Enterprise AI & Data Strategy"
            image_path = generate_linkedin_image(metadata, subtitle=subtitle)
            logger.info("Generated temp graphic for scheduled publication: %s", image_path)
        except Exception as img_err:
            logger.error("Failed to generate publication graphic in daily pipeline: %s", img_err)

        try:
            result = await publish_post(access_token, author_urn, draft_text, settings, image_path)
        finally:
            if image_path and os.path.exists(image_path):
                try:
                    os.remove(image_path)
                    logger.info("Cleaned up temp scheduled publication graphic: %s", image_path)
                except Exception as clean_err:
                    logger.error("Failed to delete temp graphic %s: %s", image_path, clean_err)

        steps["publish"] = "success" if result["success"] else f"failed: {result.get('error', '')}"

        # 10. Record post history
        post_status = "published" if result["success"] else "failed"
        await record_post(
            session,
            user_id=user_id,
            draft_id=draft.id,
            status=post_status,
            linkedin_post_id=result.get("post_id"),
            content=draft_text,
            date_for=date_for,
            error=result.get("error"),
        )
        steps["record_post"] = post_status

        # 11. Record scheduler run
        final_status = "success" if result["success"] else "failed"
        error_msg = result.get("error") if not result["success"] else None
        await record_scheduler_run(session, run_type, final_status, error_msg, steps)

        if own_session:
            await session.commit()

        logger.info("Daily pipeline completed", extra={"user_id": user_id, "status": final_status})
        return {"status": final_status, "steps": steps}

    except Exception as exc:
        steps["error"] = str(exc)
        logger.exception("Daily pipeline failed with exception", extra={"user_id": user_id})
        try:
            await record_scheduler_run(session, run_type, "failed", str(exc), steps)
            if own_session:
                await session.commit()
        except Exception:
            logger.exception("Failed to record scheduler run after pipeline error")
        return {"status": "failed", "error": str(exc), "steps": steps}

    finally:
        if own_session:
            await session.close()


async def record_scheduler_run(
    db: AsyncSession,
    run_type: str,
    status: str,
    error: str | None,
    steps: dict,
) -> SchedulerRun:
    """Save a scheduler execution record."""
    run = SchedulerRun(
        run_type=run_type,
        status=status,
        completed_at=now_phoenix(),
        steps_json=json.dumps(steps),
        error_message=error,
    )
    db.add(run)
    await db.flush()
    logger.info("Recorded scheduler run", extra={"run_type": run_type, "status": status})
    return run
