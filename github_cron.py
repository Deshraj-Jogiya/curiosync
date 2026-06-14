"""Standalone GitHub Actions cron runner script.

Seeds an in-memory database with credentials from environment variables,
and runs the daily publishing pipeline.
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta

from app.config import get_settings
from app.database import init_db, async_session
from app.models.user import User
from app.models.token import OAuthToken
from app.services.scheduler_service import run_daily_pipeline
from app.utils.logging import logger


def write_run_log(result: dict):
    """Write/append the pipeline execution history to a markdown file."""
    try:
        import os
        log_file = "run_log.md"
        if not os.path.exists(log_file):
            with open(log_file, "w", encoding="utf-8") as f:
                f.write("# 📋 CurioSync Execution History\n\nAutomated execution history of the CurioSync daily publisher.\n\n| Date (UTC) | Status | Details |\n|---|---|---|\n")
        
        from datetime import datetime
        date_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        status = result.get("status", "unknown").upper()
        
        # Clean steps for Markdown table representation
        steps_dict = result.get("steps", {})
        steps_summary = ", ".join(f"{k}: {v}" for k, v in steps_dict.items()) if steps_dict else result.get("error", "Unknown details")
        steps_summary = steps_summary.replace("|", "\\|").replace("\n", " ")
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"| {date_str} | **{status}** | {steps_summary} |\n")
        logger.info("Daily execution logged to run_log.md")
    except Exception as exc:
        logger.error("Failed to write to run_log.md: %s", exc)


async def main():
    logger.info("Initializing GitHub Actions Daily Post Cron Job")

    # Verify key environment variables are set
    access_token = os.getenv("LINKEDIN_ACCESS_TOKEN")
    sub_urn = os.getenv("LINKEDIN_SUB_URN")
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if not access_token:
        logger.error("LINKEDIN_ACCESS_TOKEN environment variable is not set!")
        sys.exit(1)
        return
    if not sub_urn:
        logger.error("LINKEDIN_SUB_URN environment variable is not set!")
        sys.exit(1)
        return
    if not openai_api_key:
        logger.error("OPENAI_API_KEY environment variable is not set!")
        sys.exit(1)
        return

    # Normalize the URN to extract the raw sub ID
    raw_sub = sub_urn
    if raw_sub.startswith("urn:li:person:"):
        raw_sub = raw_sub.replace("urn:li:person:", "")

    # 1. Initialize the SQLite in-memory database
    logger.info("Initializing in-memory database...")
    await init_db()

    # 2. Seed the database with the user and the encrypted access token
    settings = get_settings()
    try:
        encrypted_token = OAuthToken.encrypt_token(access_token, settings.fernet_key)
    except Exception as exc:
        logger.exception("Failed to encrypt access token using Fernet key!")
        sys.exit(1)
        return

    async with async_session() as session:
        # Check if user already exists to avoid IntegrityErrors
        from sqlalchemy import select
        res = await session.execute(select(User).where(User.linkedin_sub == raw_sub))
        user = res.scalars().first()

        if user is None:
            user = User(
                linkedin_sub=raw_sub,
                name="GitHub Actions Publisher",
                email="actions@github.local",
            )
            session.add(user)
            await session.flush()
        else:
            logger.info("Found existing user in database, reusing user record.")

        # Remove any existing tokens for this user to avoid conflicts
        from sqlalchemy import delete
        await session.execute(delete(OAuthToken).where(OAuthToken.user_id == user.id))

        # Create token record
        token_record = OAuthToken(
            user_id=user.id,
            encrypted_access_token=encrypted_token,
            token_type="Bearer",
            expires_at=datetime.utcnow() + timedelta(days=60),
            scopes="openid profile email w_member_social",
        )
        session.add(token_record)
        await session.commit()
        
        user_id = user.id
        logger.info("Database seeded with user (ID: %d) & encrypted token.", user_id)

    # 3. Run the standard pipeline
    logger.info("Executing daily posting pipeline...")
    result = await run_daily_pipeline(user_id=user_id, run_type="github_actions_cron")

    # Write execution log entry
    write_run_log(result)

    # 4. Handle result
    if result.get("status") == "success":
        logger.info("GitHub Actions Daily Post Cron completed successfully!")
        logger.info("Pipeline steps executed: %s", result.get("steps"))
        sys.exit(0)
    elif result.get("status") == "skipped":
        logger.info("GitHub Actions Daily Post Cron skipped: %s", result.get("reason"))
        sys.exit(0)
    else:
        logger.error("GitHub Actions Daily Post Cron failed! Error: %s", result.get("error"))
        logger.error("Pipeline steps detail: %s", result.get("steps"))
        sys.exit(1)


if __name__ == "__main__":
    # Ensure event loop policy or runner runs properly
    asyncio.run(main())
