"""Daily pipeline orchestration and scheduler run recording."""

import json
import os
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import async_session
from app.models.draft import Draft
from app.models.user import User
from app.models.scheduler_run import SchedulerRun
from app.services.auth_service import get_valid_token
from app.services.compliance_service import check_compliance
from app.services.deduplication_service import deduplicate_news
from app.services.linkedin_service import publish_post
from app.services.news_service import fetch_news, save_news_items
from app.services.post_history_service import get_today_post, record_post
from app.services.profile_source import ProfileUnavailable, load_profile
from app.services.post_plan import append_history, load_history
from app.services.post_rules import first_words
from app.services.post_visual import build_visual
from app.services.summarizer_service import DraftRejected, generate_post, post_format_for, source_text
from app.utils.logging import logger
from app.utils.timezone import now_phoenix, today_phoenix


async def run_daily_pipeline(
    user_id: int,
    db: AsyncSession | None = None,
    settings: Settings | None = None,
    run_type: str = "scheduled",
    publish: bool = False,
    draft_format: str | None = None,
    draft_day: date | None = None,
    extra_history: list[dict] | None = None,
    use_stories: bool = False,
) -> dict:
    """Orchestrate the daily post pipeline.

    When called from the scheduler (no db/settings args), opens its own session.
    When called from a route (db/settings provided), uses the provided session.

    publish=False (the default) stops after the draft and its graphic are made and returns them with status "drafted", so a person
    approves each post before it goes out; LinkedIn's API terms do not allow unattended automated posting. Only a caller acting on a
    person's explicit click (the web app's Run now button, or the approved publish job) passes publish=True.

    draft_format drafts a post of that format whatever today is, for draft_day (default today), skipping the already-posted check: the
    GitHub runner drafts ahead for the next open post day and for previews. extra_history (approved posts not yet published) counts as
    history, so a new draft does not repeat their subject or opener.

    use_stories (the GitHub runner) writes the post from one story in data/stories.json (see story_bank), refilling the bank from the
    projects' repositories when it runs low, and charts that story's numbers as the image. With no story ready nothing is drafted:
    a post built from resume bullets is the weak draft this replaces.
    """
    settings = settings or get_settings()
    own_session = db is None

    if own_session:
        session = async_session()
    else:
        session = db

    date_for = draft_day or today_phoenix()
    steps: dict[str, str] = {}

    logger.info("Starting daily pipeline", extra={"user_id": user_id, "date_for": str(date_for), "run_type": run_type})

    try:
        # 1. Check duplicate
        existing = None if draft_format else await get_today_post(session, user_id, date_for)
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

        fmt = draft_format or post_format_for(date_for)
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
        if fmt == "decision":
            # News is only a rare exception (see summarizer_service): fetch it on Fridays, and carry on without it if the fetch fails.
            try:
                news_items = await fetch_news(settings)
                deduped = deduplicate_news(news_items) if news_items else []
                steps["fetch_news"] = f"{len(deduped)} items"
                if deduped:
                    await save_news_items(session, deduped, date_for)
            except Exception as exc:
                steps["fetch_news"] = f"unavailable ({exc}); no news exception today"

        history = load_history() + list(extra_history or [])
        story, story_item, feedback = None, None, []
        if use_stories:
            from app.services.post_plan import candidates, load_notes
            from app.services.story_bank import load_feedback, pick_story, refill

            items = candidates(profile, "project", load_notes())
            try:
                steps["stories"] = await refill(items, history, settings)
            except Exception as exc:
                steps["stories"] = f"refill failed ({exc})"
            picked = pick_story(items, history)
            if picked is None:
                steps["generate_draft"] = "no story ready; nothing drafted"
                await record_scheduler_run(session, run_type, "skipped", "No story ready", steps)
                if own_session:
                    await session.commit()
                return {"status": "skipped", "reason": "No story is ready to write from.", "steps": steps}
            story, story_item = picked
            feedback = [f["comment"] for f in load_feedback()[-8:] if f.get("comment")]
        try:
            post = await generate_post(fmt, profile, settings, date_for, deduped, history, story=story, item=story_item,
                                       feedback=feedback)
        except DraftRejected as exc:
            steps["generate_draft"] = f"rejected after rewrites: {exc.problems}"
            await record_scheduler_run(session, run_type, "skipped", "Draft failed the post rules", steps)
            if own_session:
                await session.commit()
            return {"status": "skipped", "reason": f"No draft passed the post rules: {exc.problems}", "steps": steps}
        draft_text, subject, fmt = post["text"], post["subject"], post["format"]
        steps["generate_draft"] = (f"{fmt} about {subject}{' (story ' + story['id'] + ')' if story else ''} "
                                   f"(hook {post['hook_type']}, {len(draft_text)} chars, {post['attempts']} model calls)")

        compliance = check_compliance(draft_text, deduped)
        steps["compliance_check"] = "passed" if not compliance["blocking"] else f"blocked: {compliance['blocking']}"
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

        image_path, alt_text, visual_kind = None, None, "none"
        try:
            if story:
                # The image charts the same story the post tells, using only numbers the post states; no chart, no image.
                from app.services.post_visual import render_story_chart

                chart = render_story_chart(story, post["item"], draft_text)
                if chart:
                    image_path, alt_text, visual_kind = chart[0], chart[1], "story chart"
            else:
                image_path, alt_text, visual_kind = await build_visual(post["item"], settings,
                                                                       source_text(profile, post["item"], post["news"]))
        except Exception as img_err:
            logger.error("Failed to build the post image: %s", img_err)
        steps["visual"] = visual_kind

        history_entry = {
            "date": str(date_for),
            "format": fmt,
            "subject": subject,
            "hook_type": post["hook_type"],
            "opener_words": first_words(draft_text),
            "text": draft_text,
        }
        if story:
            history_entry["story_id"] = story["id"]

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
                "alt_text": alt_text,
                "visual": visual_kind,
                "history_entry": history_entry,
                "compliance": compliance,
                "steps": steps,
            }

        try:
            result = await publish_post(access_token, author_urn, draft_text, settings, image_path, alt_text)
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
        if result["success"]:
            append_history(history_entry)

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
