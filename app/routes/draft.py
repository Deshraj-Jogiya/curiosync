"""Draft generation and rewrite routes."""

import json
import os
import shutil
import time
from fastapi import APIRouter, Request, Depends, Form
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select
from app.config import Settings, get_settings
from app.database import get_db
from app.models.draft import Draft
from app.models.source import NewsSource
from app.services.summarizer_service import generate_draft, validate_draft_length
from app.services.rewrite_service import rewrite_draft
from app.services.compliance_service import humanize_draft, check_compliance
from app.utils.logging import logger
from app.utils.timezone import today_phoenix

router = APIRouter(prefix="/draft", tags=["draft"])
templates = Jinja2Templates(directory="app/templates")


@router.post("/generate")
async def generate(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Generate a LinkedIn post draft from today's fetched news."""
    try:
        date_for = today_phoenix()
        stmt = select(NewsSource).where(NewsSource.date_for == date_for)
        result = await db.execute(stmt)
        news_sources = result.scalars().all()

        if not news_sources:
            return templates.TemplateResponse(
                "partials/draft_panel.html",
                {
                    "request": request,
                    "content": None,
                    "error": "No news items found. Fetch today's news first.",
                },
            )

        news_items = [
            {
                "title": ns.title,
                "url": ns.url,
                "source_name": ns.source_name,
                "summary": ns.summary,
            }
            for ns in news_sources
        ]

        logger.info("Generating draft from %d news items", len(news_items))
        raw_draft = await generate_draft(news_items, settings)
        draft_text = humanize_draft(raw_draft)
        compliance = check_compliance(draft_text, news_items)
        valid, word_count = validate_draft_length(draft_text)

        date_for = today_phoenix()
        char_count = len(draft_text)

        draft = Draft(
            user_id=request.session.get("user_id", 1),
            content=draft_text,
            word_count=word_count,
            char_count=char_count,
            tone="professional",
            sources_json=json.dumps(news_items),
            compliance_passed=compliance["passed"],
            date_for=date_for,
        )
        db.add(draft)
        await db.flush()

        request.session["current_draft_id"] = draft.id
        request.session["current_draft"] = draft_text

        # Generate static graphic preview
        user_id = request.session.get("user_id", 1)
        image_url = None
        try:
            from app.services.image_service import parse_draft_for_image, generate_linkedin_image
            title, bullets = parse_draft_for_image(draft_text)
            subtitle = "Monday Project Spotlight" if ("spotlight" in draft_text.lower() or "project" in draft_text.lower()) else "Enterprise AI & Data Strategy"
            temp_path = generate_linkedin_image(title, bullets, subtitle)
            os.makedirs("app/static/generated", exist_ok=True)
            static_path = f"app/static/generated/draft_{user_id}.png"
            if os.path.exists(static_path):
                os.remove(static_path)
            shutil.move(temp_path, static_path)
            image_url = f"/static/generated/draft_{user_id}.png"
            logger.info("Saved static graphic preview to %s", static_path)
        except Exception as img_err:
            logger.error("Failed to generate static preview: %s", img_err)

        logger.info("Draft generated: %d words, %d chars, compliance=%s", word_count, char_count, compliance["passed"])

        return templates.TemplateResponse(
            "partials/draft_panel.html",
            {
                "request": request,
                "content": draft_text,
                "word_count": word_count,
                "char_count": char_count,
                "compliance": compliance,
                "draft_id": draft.id,
                "image_url": image_url,
                "timestamp": int(time.time()),
            },
        )

    except Exception as e:
        logger.error("Draft generation failed: %s", str(e))
        return templates.TemplateResponse(
            "partials/draft_panel.html",
            {"request": request, "content": None, "error": f"Failed to generate draft: {str(e)}"},
        )


@router.post("/rewrite")
async def rewrite(
    request: Request,
    tone: str = Form("professional"),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Rewrite the current draft with a different tone."""
    try:
        current_draft = request.session.get("current_draft")
        date_for = today_phoenix()
        stmt = select(NewsSource).where(NewsSource.date_for == date_for)
        result = await db.execute(stmt)
        news_sources = result.scalars().all()
        news_items = [
            {
                "title": ns.title,
                "url": ns.url,
                "source_name": ns.source_name,
                "summary": ns.summary,
            }
            for ns in news_sources
        ]

        if not current_draft:
            return templates.TemplateResponse(
                "partials/draft_panel.html",
                {"request": request, "content": None, "error": "No draft to rewrite. Generate one first."},
            )

        logger.info("Rewriting draft with tone: %s", tone)
        rewritten = await rewrite_draft(current_draft, tone, news_items, settings)
        rewritten = humanize_draft(rewritten)
        compliance = check_compliance(rewritten, news_items)
        valid, word_count = validate_draft_length(rewritten)
        char_count = len(rewritten)

        date_for = today_phoenix()
        draft = Draft(
            user_id=request.session.get("user_id", 1),
            content=rewritten,
            word_count=word_count,
            char_count=char_count,
            tone=tone,
            sources_json=json.dumps(news_items),
            compliance_passed=compliance["passed"],
            date_for=date_for,
        )
        db.add(draft)
        await db.flush()

        request.session["current_draft_id"] = draft.id
        request.session["current_draft"] = rewritten

        # Generate static graphic preview
        user_id = request.session.get("user_id", 1)
        image_url = None
        try:
            from app.services.image_service import parse_draft_for_image, generate_linkedin_image
            title, bullets = parse_draft_for_image(rewritten)
            subtitle = "Monday Project Spotlight" if ("spotlight" in rewritten.lower() or "project" in rewritten.lower()) else "Enterprise AI & Data Strategy"
            temp_path = generate_linkedin_image(title, bullets, subtitle)
            os.makedirs("app/static/generated", exist_ok=True)
            static_path = f"app/static/generated/draft_{user_id}.png"
            if os.path.exists(static_path):
                os.remove(static_path)
            shutil.move(temp_path, static_path)
            image_url = f"/static/generated/draft_{user_id}.png"
            logger.info("Saved static graphic preview to %s", static_path)
        except Exception as img_err:
            logger.error("Failed to generate static preview: %s", img_err)

        return templates.TemplateResponse(
            "partials/draft_panel.html",
            {
                "request": request,
                "content": rewritten,
                "word_count": word_count,
                "char_count": char_count,
                "compliance": compliance,
                "draft_id": draft.id,
                "tone": tone,
                "image_url": image_url,
                "timestamp": int(time.time()),
            },
        )

    except Exception as e:
        logger.error("Rewrite failed: %s", str(e))
        return templates.TemplateResponse(
            "partials/draft_panel.html",
            {"request": request, "content": request.session.get("current_draft"), "error": f"Rewrite failed: {str(e)}"},
        )
