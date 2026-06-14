"""HTML page routes for the web UI."""

from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    """Serve the main dashboard page."""
    user_id = request.session.get("user_id")
    if not user_id:
        return templates.TemplateResponse("login.html", {"request": request})

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user_name": request.session.get("user_name"),
        },
    )


@router.get("/login")
async def login_page(request: Request):
    """Serve the login page."""
    return templates.TemplateResponse("login.html", {"request": request})
