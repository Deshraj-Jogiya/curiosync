"""Post history routes."""

from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.post_history_service import get_history

router = APIRouter(prefix="/history", tags=["history"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
async def history_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Render the full post history page."""
    user_id = request.session.get("user_id")
    posts = []
    if user_id:
        posts = await get_history(db, user_id, limit=50)

    return templates.TemplateResponse(
        "history.html",
        {"request": request, "posts": posts, "user_name": request.session.get("user_name")},
    )
