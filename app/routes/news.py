"""News fetching routes."""

from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.services.news_service import fetch_news, save_news_items
from app.services.deduplication_service import deduplicate_news
from app.utils.logging import logger
from app.utils.timezone import today_phoenix

router = APIRouter(prefix="/news", tags=["news"])
templates = Jinja2Templates(directory="app/templates")


@router.post("/fetch-today")
async def fetch_today(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Fetch today's top 15 tech news items and return as HTMX partial."""
    try:
        logger.info("Fetching today's tech news")
        raw_items = await fetch_news(settings)
        items = deduplicate_news(raw_items)
        items = items[:15]

        date_for = today_phoenix()
        await save_news_items(db, items, date_for)
        await db.commit()

        # Store in session for draft generation
        request.session["news_items"] = items
        request.session["news_date"] = date_for.isoformat()

        logger.info("Fetched and deduplicated %d news items", len(items))
        return templates.TemplateResponse(
            "partials/news_panel.html",
            {"request": request, "items": items, "count": len(items)},
        )

    except Exception as e:
        logger.error("News fetch failed: %s", str(e))
        return templates.TemplateResponse(
            "partials/toast.html",
            {"request": request, "message": f"Failed to fetch news: {str(e)}", "type": "error"},
        )
