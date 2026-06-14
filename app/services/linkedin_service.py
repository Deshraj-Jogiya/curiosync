"""LinkedIn publishing service."""

import os
from datetime import date

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.post_history import PostHistory
from app.utils.logging import logger


async def publish_post(
    access_token: str,
    author_urn: str,
    text: str,
    settings: Settings,
    image_path: str = None,
) -> dict:
    """Publish a post to LinkedIn via the Posts API, optionally with an image."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": "202605",
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }

    image_urn = None
    if image_path and os.path.exists(image_path):
        try:
            logger.info("Initializing image upload for %s", image_path)
            # Step 1: Initialize upload
            init_url = "https://api.linkedin.com/rest/images?action=initializeUpload"
            init_body = {
                "initializeUploadRequest": {
                    "owner": author_urn
                }
            }
            async with httpx.AsyncClient(timeout=30) as client:
                init_resp = await client.post(init_url, json=init_body, headers=headers)

            if init_resp.status_code == 200:
                init_data = init_resp.json()
                upload_url = init_data.get("value", {}).get("uploadUrl")
                image_urn = init_data.get("value", {}).get("image")

                if upload_url and image_urn:
                    logger.info("Uploading image bytes to %s", upload_url)
                    # Step 2: Upload raw image binary
                    with open(image_path, "rb") as f:
                        image_bytes = f.read()

                    async with httpx.AsyncClient(timeout=60) as client:
                        upload_resp = await client.put(upload_url, content=image_bytes, headers={"Content-Type": "image/png"})

                    if upload_resp.status_code in (200, 201, 204):
                        logger.info("Image bytes uploaded successfully. URN: %s", image_urn)
                    else:
                        logger.error("Failed to upload image bytes. Status: %d, Response: %s", upload_resp.status_code, upload_resp.text)
                        image_urn = None
                else:
                    logger.error("Could not find uploadUrl or image URN in response: %s", init_data)
                    image_urn = None
            else:
                logger.error("Failed to initialize image upload. Status: %d, Response: %s", init_resp.status_code, init_resp.text)
                image_urn = None
        except Exception as e:
            logger.exception("Error uploading image to LinkedIn: %s", str(e))
            image_urn = None

    body = {
        "author": author_urn,
        "commentary": text,
        "visibility": "PUBLIC",
        "distribution": {"feedDistribution": "MAIN_FEED"},
        "lifecycleState": "PUBLISHED",
    }

    if image_urn:
        body["content"] = {
            "media": {
                "id": image_urn,
                "altText": "Technical insight card for the post"
            }
        }

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
