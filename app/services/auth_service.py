"""LinkedIn OAuth2 authentication service."""

import secrets
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.token import OAuthToken
from app.models.user import User
from app.utils.logging import logger


async def get_authorization_url(settings: Settings) -> tuple[str, str]:
    """Build LinkedIn OAuth authorization URL with a random state parameter."""
    state = secrets.token_urlsafe(32)
    params = {
        "response_type": "code",
        "client_id": settings.linkedin_client_id,
        "redirect_uri": settings.linkedin_redirect_uri,
        "state": state,
        "scope": "openid profile email w_member_social",
    }
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{settings.linkedin_auth_url}?{qs}"
    logger.info("Generated LinkedIn authorization URL", extra={"state": state})
    return url, state


async def exchange_code_for_token(code: str, settings: Settings) -> dict:
    """Exchange an authorization code for an access token."""
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.linkedin_redirect_uri,
        "client_id": settings.linkedin_client_id,
        "client_secret": settings.linkedin_client_secret,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            settings.linkedin_token_url,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info("Token exchange successful", extra={"expires_in": data.get("expires_in")})
        return data


async def get_user_profile(access_token: str) -> dict:
    """Fetch the authenticated user's profile from LinkedIn."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            "https://api.linkedin.com/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        profile = resp.json()
        logger.info("Fetched LinkedIn profile", extra={"sub": profile.get("sub")})
        return profile


async def store_token(
    db: AsyncSession,
    user_id: int,
    token_data: dict,
    settings: Settings,
) -> OAuthToken:
    """Encrypt and persist an OAuth token, replacing any existing one for the user."""
    encrypted = OAuthToken.encrypt_token(token_data["access_token"], settings.fernet_key)
    expires_in = token_data.get("expires_in", 5184000)  # default 60 days
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    # Remove old tokens for this user
    existing = await db.execute(select(OAuthToken).where(OAuthToken.user_id == user_id))
    for old_token in existing.scalars().all():
        await db.delete(old_token)

    token = OAuthToken(
        user_id=user_id,
        encrypted_access_token=encrypted,
        token_type=token_data.get("token_type", "Bearer"),
        expires_at=expires_at,
        scopes=token_data.get("scope"),
    )
    db.add(token)
    await db.flush()
    logger.info("Stored encrypted token", extra={"user_id": user_id, "expires_at": str(expires_at)})
    return token


async def get_valid_token(
    db: AsyncSession,
    user_id: int,
    settings: Settings,
) -> str | None:
    """Retrieve and decrypt the user's access token. Returns None if expired or missing."""
    result = await db.execute(
        select(OAuthToken)
        .where(OAuthToken.user_id == user_id)
        .order_by(OAuthToken.created_at.desc())
    )
    token = result.scalars().first()
    if token is None:
        logger.warning("No token found", extra={"user_id": user_id})
        return None

    if token.is_expired:
        logger.warning("Token expired", extra={"user_id": user_id, "expires_at": str(token.expires_at)})
        return None

    try:
        decrypted = token.decrypt_access_token(settings.fernet_key)
        return decrypted
    except Exception:
        logger.exception("Failed to decrypt token", extra={"user_id": user_id})
        return None


async def get_or_create_user(db: AsyncSession, profile_data: dict) -> User:
    """Upsert a user record from LinkedIn profile data."""
    sub = profile_data["sub"]
    result = await db.execute(select(User).where(User.linkedin_sub == sub))
    user = result.scalars().first()

    if user is None:
        user = User(
            linkedin_sub=sub,
            name=profile_data.get("name", ""),
            email=profile_data.get("email"),
            picture_url=profile_data.get("picture"),
        )
        db.add(user)
        await db.flush()
        logger.info("Created new user", extra={"user_id": user.id, "sub": sub})
    else:
        user.name = profile_data.get("name", user.name)
        user.email = profile_data.get("email", user.email)
        user.picture_url = profile_data.get("picture", user.picture_url)
        await db.flush()
        logger.info("Updated existing user", extra={"user_id": user.id, "sub": sub})

    return user
