"""LinkedIn publishing route."""

import os
from fastapi import APIRouter, Request, Depends, Form
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.services.auth_service import get_valid_token
from app.services.linkedin_service import publish_post, check_duplicate_post
from app.services.post_history_service import record_post
from app.utils.logging import logger
from app.utils.timezone import today_phoenix

router = APIRouter(prefix="/linkedin", tags=["linkedin"])
templates = Jinja2Templates(directory="app/templates")


@router.post("/publish")
async def publish(
    request: Request,
    content: str = Form(None),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Publish the current draft to LinkedIn."""
    user_id = request.session.get("user_id")
    if not user_id:
        return templates.TemplateResponse(
            "partials/toast.html",
            {"request": request, "message": "Not authenticated. Please sign in with LinkedIn.", "type": "error"},
        )

    draft_text = content or request.session.get("current_draft")
    draft_id = request.session.get("current_draft_id")

    if not draft_text:
        return templates.TemplateResponse(
            "partials/toast.html",
            {"request": request, "message": "No draft to publish. Generate one first.", "type": "error"},
        )

    date_for = today_phoenix()

    # Duplicate prevention
    is_duplicate = await check_duplicate_post(db, user_id, date_for)
    if is_duplicate:
        logger.warning("Duplicate post prevented for user %s on %s", user_id, date_for)
        return templates.TemplateResponse(
            "partials/toast.html",
            {"request": request, "message": "A post was already published today. Duplicate prevented.", "type": "warning"},
        )

    # Get valid token
    access_token = await get_valid_token(db, user_id, settings)
    if not access_token:
        logger.warning("Token expired for user %s", user_id)
        return templates.TemplateResponse(
            "partials/toast.html",
            {"request": request, "message": "LinkedIn token expired. Please re-authorize.", "type": "error"},
        )

    try:
        # Get LinkedIn sub from session or DB
        from sqlalchemy import select
        from app.models.user import User

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return templates.TemplateResponse(
                "partials/toast.html",
                {"request": request, "message": "User not found.", "type": "error"},
            )

        author_urn = f"urn:li:person:{user.linkedin_sub}"
        
        # Generate custom high-engagement graphic on the fly
        image_path = None
        try:
            from app.services.image_service import parse_draft_for_image, generate_linkedin_image
            title, bullets = parse_draft_for_image(draft_text)
            subtitle = "Monday Project Spotlight" if ("spotlight" in draft_text.lower() or "project" in draft_text.lower()) else "Enterprise AI & Data Strategy"
            image_path = generate_linkedin_image(title, bullets, subtitle)
            logger.info("Generated temp graphic for publication: %s", image_path)
        except Exception as img_err:
            logger.error("Failed to generate publication graphic: %s", img_err)

        try:
            publish_result = await publish_post(access_token, author_urn, draft_text, settings, image_path)
        finally:
            if image_path and os.path.exists(image_path):
                try:
                    os.remove(image_path)
                    logger.info("Cleaned up temp publication graphic: %s", image_path)
                except Exception as clean_err:
                    logger.error("Failed to delete temp graphic %s: %s", image_path, clean_err)

        if publish_result["success"]:
            await record_post(
                db, user_id, draft_id, "published",
                publish_result.get("post_id"), draft_text, date_for, None,
            )
            await db.commit()
            logger.info("Post published: %s", publish_result.get("post_id"))
            return templates.TemplateResponse(
                "partials/toast.html",
                {"request": request, "message": "Post published successfully! 🎉", "type": "success"},
            )
        else:
            error_msg = publish_result.get("error", "Unknown error")
            await record_post(
                db, user_id, draft_id, "failed",
                None, draft_text, date_for, error_msg,
            )
            await db.commit()
            logger.error("Publish failed: %s", error_msg)
            return templates.TemplateResponse(
                "partials/toast.html",
                {"request": request, "message": f"Publish failed: {error_msg}", "type": "error"},
            )

    except Exception as e:
        logger.error("Publish error: %s", str(e))
        await record_post(
            db, user_id, draft_id, "failed",
            None, draft_text, date_for, str(e),
        )
        await db.commit()
        return templates.TemplateResponse(
            "partials/toast.html",
            {"request": request, "message": f"Publish error: {str(e)}", "type": "error"},
        )
