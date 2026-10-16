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
from app.services.profile_source import ProfileUnavailable, load_profile
from app.services.summarizer_service import generate_post, post_format_for
from app.utils.logging import logger
from app.utils.timezone import now_phoenix, today_phoenix


async def run_daily_pipeline(
    user_id: int,
    db: AsyncSession | None = None,
    settings: Settings | None = None,
    run_type: str = "scheduled",
    publish: bool = False,
) -> dict:
    """Orchestrate the daily post pipeline.

    When called from the scheduler (no db/settings args), opens its own session.
    When called from a route (db/settings provided), uses the provided session.

    publish=False (the default) stops after the draft and its graphic are made and returns them with status "drafted", so a person
    approves each post before it goes out; LinkedIn's API terms do not allow unattended automated posting. Only a caller acting on a
    person's explicit click (the web app's Run now button, or the approved publish job) passes publish=True.
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

        fmt = post_format_for(date_for)
        if fmt is None:
            steps["schedule"] = f"no post scheduled on {date_for:%A}"
            await record_scheduler_run(session, run_type, "skipped", None, steps)
            if own_session:
                await session.commit()
            return {"status": "skipped", "reason": f"No post is scheduled on {date_for:%A}.", "steps": steps}
        steps["schedule"] = fmt

        try:
            profile = await load_profile()
        except ProfileUnavailable as exc:
            steps["profile"] = f"failed — {exc}"
            await record_scheduler_run(session, run_type, "failed", str(exc), steps)
            if own_session:
                await session.commit()
            return {"status": "failed", "error": f"Profile unavailable, no post drafted: {exc}", "steps": steps}
        steps["profile"] = "loaded"

        deduped: list[dict] = []
        if fmt == "news_take":
            news_items = await fetch_news(settings)
            if not news_items:
                steps["fetch_news"] = "failed — no items returned"
                logger.error("Pipeline failed — no news items fetched")
                await record_scheduler_run(session, run_type, "failed", "No news items", steps)
                if own_session:
                    await session.commit()
                return {"status": "failed", "error": "No tech news found for today.", "steps": steps}
            steps["fetch_news"] = f"fetched {len(news_items)} items"
            deduped = deduplicate_news(news_items)
            steps["deduplication"] = f"{len(news_items)} -> {len(deduped)} items"
            await save_news_items(session, deduped, date_for)
            steps["save_news"] = f"saved {len(deduped)} items"

        draft_text, subject = await generate_post(fmt, profile, settings, date_for, deduped)
        steps["generate_draft"] = f"{fmt} about {subject} ({len(draft_text.split())} words)"

        # Humanize first (it also strips links and corrects tenure claims), then check the text that would actually go out.
        draft_text = humanize_draft(draft_text)
        steps["humanize"] = "applied"
        compliance = check_compliance(draft_text, deduped)
        steps["compliance_check"] = "passed" if compliance["passed"] else f"issues: {compliance['issues']}"
        if compliance["blocking"]:
            await record_scheduler_run(session, run_type, "failed", "Blocked by compliance", steps)
            if own_session:
                await session.commit()
            return {"status": "failed", "error": f"Draft blocked: {compliance['blocking']}", "steps": steps}
        sources_list = [{"title": i["title"], "source_name": i["source_name"]} for i in deduped]

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

        # Publish to LinkedIn
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

        if not publish:
            await record_scheduler_run(session, run_type, "drafted", None, steps)
            if own_session:
                await session.commit()
            return {
                "status": "drafted",
                "format": fmt,
                "subject": subject,
                "draft": draft_text,
                "image_path": image_path,
                "compliance": compliance,
                "steps": steps,
            }

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
