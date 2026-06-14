"""Post history service for recording and querying publish attempts."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.post_history import PostHistory
from app.utils.logging import logger


async def record_post(
    db: AsyncSession,
    user_id: int,
    draft_id: int | None,
    status: str,
    linkedin_post_id: str | None,
    content: str,
    date_for: date,
    error: str | None = None,
) -> PostHistory:
    """Create and persist a PostHistory record."""
    record = PostHistory(
        user_id=user_id,
        draft_id=draft_id,
        linkedin_post_id=linkedin_post_id,
        status=status,
        content=content,
        date_for=date_for,
        error_message=error,
    )
    db.add(record)
    await db.flush()
    logger.info(
        "Recorded post history",
        extra={"user_id": user_id, "status": status, "date_for": str(date_for)},
    )
    return record


async def get_history(
    db: AsyncSession,
    user_id: int,
    limit: int = 20,
    offset: int = 0,
) -> list[PostHistory]:
    """Retrieve paginated post history ordered by most recent first."""
    result = await db.execute(
        select(PostHistory)
        .where(PostHistory.user_id == user_id)
        .order_by(PostHistory.published_at.desc())
        .limit(limit)
        .offset(offset)
    )
    records = list(result.scalars().all())
    logger.info("Fetched post history", extra={"user_id": user_id, "count": len(records)})
    return records


async def get_today_post(
    db: AsyncSession,
    user_id: int,
    date_for: date,
) -> PostHistory | None:
    """Check whether a post was already published today."""
    result = await db.execute(
        select(PostHistory).where(
            PostHistory.user_id == user_id,
            PostHistory.date_for == date_for,
            PostHistory.status == "published",
        )
    )
    return result.scalars().first()
