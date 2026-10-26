"""LinkedIn publishing service."""

import os
from datetime import date

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.post_history import PostHistory
from app.utils.logging import logger


# The Posts API reads "commentary" as Little Text Format, where these characters are markup; unescaped, the post is cut off at the first
# one. Hashtags written as plain "#tag" are kept as they are, which is how LinkedIn's own clients send them.
_LITTLE_TEXT_RESERVED = "\\|{}@[]()<>*_~"


def escape_little_text(text: str) -> str:
    return "".join("\\" + ch if ch in _LITTLE_TEXT_RESERVED else ch for ch in text)


async def _upload(kind: str, path: str, owner: str, headers: dict) -> str | None:
    """Upload a file through LinkedIn's images or documents API and return its URN (urn:li:image or urn:li:document), or None."""
    field = "image" if kind == "images" else "document"
    content_type = "image/png" if kind == "images" else "application/pdf"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            init = await client.post(f"https://api.linkedin.com/rest/{kind}?action=initializeUpload",
                                     json={"initializeUploadRequest": {"owner": owner}}, headers=headers)
        if init.status_code != 200:
            logger.error("Failed to initialize %s upload. Status: %d, Response: %s", field, init.status_code, init.text)
            return None
        value = init.json().get("value", {})
        upload_url, urn = value.get("uploadUrl"), value.get(field)
        if not (upload_url and urn):
            logger.error("No uploadUrl or %s URN in response: %s", field, value)
            return None
        with open(path, "rb") as f:
            data = f.read()
        async with httpx.AsyncClient(timeout=120) as client:
            up = await client.put(upload_url, content=data, headers={"Authorization": headers["Authorization"],
                                                                     "Content-Type": content_type})
        if up.status_code not in (200, 201, 204):
            logger.error("Failed to upload %s bytes. Status: %d, Response: %s", field, up.status_code, up.text)
            return None
        logger.info("Uploaded %s %s", field, urn)
        return urn
    except Exception as exc:
        logger.exception("Error uploading %s to LinkedIn: %s", field, exc)
        return None


async def publish_post(
    access_token: str,
    author_urn: str,
    text: str,
    settings: Settings,
    image_path: str = None,
    alt_text: str | None = None,
    document_path: str | None = None,
    document_title: str | None = None,
) -> dict:
    """Publish a post to LinkedIn via the Posts API with an image or a PDF document (shown as a swipeable carousel).

    The media was approved together with the text, so a failed upload fails the post instead of publishing the text alone."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": "202605",
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }

    media = None
    if document_path and os.path.exists(document_path):
        urn = await _upload("documents", document_path, author_urn, headers)
        if not urn:
            return {"success": False, "post_id": None, "error": "the approved document could not be uploaded; nothing was posted"}
        media = {"id": urn, "title": (document_title or "Project results")[:400]}
    elif image_path and os.path.exists(image_path):
        urn = await _upload("images", image_path, author_urn, headers)
        if not urn:
            return {"success": False, "post_id": None, "error": "the approved image could not be uploaded; nothing was posted"}
        media = {"id": urn, "altText": (alt_text or "Graphic summarizing the project described in the post")[:4086]}

    body = {
        "author": author_urn,
        "commentary": escape_little_text(text),
        "visibility": "PUBLIC",
        "distribution": {"feedDistribution": "MAIN_FEED"},
        "lifecycleState": "PUBLISHED",
    }
    if media:
        body["content"] = {"media": media}
    image_urn = media["id"] if media else None

    logger.info("Publishing post to LinkedIn", extra={"author_urn": author_urn, "text_length": len(text), "has_image": image_urn is not None})

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(settings.linkedin_posts_url, json=body, headers=headers)

        if resp.status_code == 201:
            post_id = resp.headers.get("x-restli-id", "")
            logger.info("Post published successfully", extra={"post_id": post_id})
            return {"success": True, "post_id": post_id, "error": None}

        if resp.status_code in (401, 403):
            error_msg = f"Authentication error ({resp.status_code}): token may be invalid or expired"
            logger.error(error_msg)
            return {"success": False, "post_id": None, "error": error_msg}

        if resp.status_code == 429:
            error_msg = "Rate limited by LinkedIn API — try again later"
            logger.warning(error_msg)
            return {"success": False, "post_id": None, "error": error_msg}

        error_msg = f"LinkedIn API returned {resp.status_code}: {resp.text[:500]}"
        logger.error(error_msg)
        return {"success": False, "post_id": None, "error": error_msg}

    except httpx.TimeoutException:
        error_msg = "Request to LinkedIn API timed out"
        logger.error(error_msg)
        return {"success": False, "post_id": None, "error": error_msg}
    except Exception as exc:
        error_msg = f"Unexpected error publishing post: {exc}"
        logger.exception(error_msg)
        return {"success": False, "post_id": None, "error": error_msg}


async def check_duplicate_post(
    db: AsyncSession,
    user_id: int,
    date_for: date,
) -> bool:
    """Check whether a post has already been published today."""
    result = await db.execute(
        select(PostHistory).where(
            PostHistory.user_id == user_id,
            PostHistory.date_for == date_for,
            PostHistory.status == "published",
        )
    )
    exists = result.scalars().first() is not None
    logger.info(
        "Duplicate post check",
        extra={"user_id": user_id, "date_for": str(date_for), "duplicate_found": exists},
    )
    return exists
