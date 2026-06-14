"""LinkedIn OAuth authentication routes."""

import secrets
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.services.auth_service import (
    get_authorization_url,
    exchange_code_for_token,
    get_user_profile,
    get_or_create_user,
    store_token,
    get_valid_token,
)
from app.utils.logging import logger

router = APIRouter(prefix="/auth/linkedin", tags=["auth"])


@router.get("/login")
async def linkedin_login(request: Request, settings: Settings = Depends(get_settings)):
    """Redirect user to LinkedIn OAuth authorization page."""
    url, state = await get_authorization_url(settings)
    request.session["oauth_state"] = state
    return RedirectResponse(url=url)


@router.get("/callback")
async def linkedin_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Handle LinkedIn OAuth callback after user authorization."""
    if error:
        logger.error("LinkedIn OAuth error: %s - %s", error, error_description)
        return RedirectResponse(url="/?error=auth_denied")

    saved_state = request.session.get("oauth_state")
    if not state or state != saved_state:
        logger.warning("OAuth state mismatch")
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    try:
        token_data = await exchange_code_for_token(code, settings)
        access_token = token_data["access_token"]

        profile = await get_user_profile(access_token)
        user = await get_or_create_user(db, profile)
        await store_token(db, user.id, token_data, settings)
        await db.commit()

        request.session["user_id"] = user.id
        request.session["user_name"] = user.name
        request.session.pop("oauth_state", None)

        logger.info("User %s authenticated successfully", user.name)
        return RedirectResponse(url="/", status_code=303)

    except Exception as e:
        logger.error("OAuth callback failed: %s", str(e))
        return RedirectResponse(url="/?error=auth_failed")


@router.post("/disconnect")
async def linkedin_disconnect(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Remove stored token and disconnect LinkedIn."""
    user_id = request.session.get("user_id")
    if user_id:
        from sqlalchemy import delete
        from app.models.token import OAuthToken

        await db.execute(delete(OAuthToken).where(OAuthToken.user_id == user_id))
        await db.commit()
        request.session.clear()
        logger.info("User %s disconnected LinkedIn", user_id)

    return RedirectResponse(url="/login", status_code=303)


@router.get("/status")
async def linkedin_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Return LinkedIn connection status as an HTMX partial."""
    from fastapi.responses import HTMLResponse
    from fastapi.templating import Jinja2Templates

    templates = Jinja2Templates(directory="app/templates")
    user_id = request.session.get("user_id")

    if not user_id:
        return templates.TemplateResponse(
            "partials/connection_status.html",
            {
                "request": request,
                "connected": False,
                "user_name": None,
                "token_expires_at": None,
                "token_expired": False,
                "token_expires_soon": False,
            },
        )

    from sqlalchemy import select
    from app.models.token import OAuthToken
    from app.models.user import User

    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()

    result = await db.execute(
        select(OAuthToken).where(OAuthToken.user_id == user_id).order_by(OAuthToken.created_at.desc())
    )
    token = result.scalar_one_or_none()

    connected = token is not None and not token.is_expired
    decrypted_token = None
    if connected:
        try:
            decrypted_token = token.decrypt_access_token(settings.fernet_key)
        except Exception:
            logger.exception("Failed to decrypt access token for UI status display")

    return templates.TemplateResponse(
        "partials/connection_status.html",
        {
            "request": request,
            "connected": connected,
            "user_name": request.session.get("user_name"),
            "token_expires_at": token.expires_at.strftime("%Y-%m-%d %H:%M") if token else None,
            "token_expired": token.is_expired if token else False,
            "token_expires_soon": token.expires_soon if token else False,
            "linkedin_sub": user.linkedin_sub if user else None,
            "access_token": decrypted_token,
        },
    )
