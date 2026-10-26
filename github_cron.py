"""Standalone GitHub Actions runner.

`python -m github_cron draft` (scheduled): seeds an in-memory database from environment variables, drafts the day's post if one is
scheduled, saves it to pending_post/ for review, and writes the TIL note. It never publishes.
`python -m github_cron publish` (runs only after the owner approves the job in GitHub): posts the saved draft unchanged.
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

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


async def generate_and_save_til(settings):
    """Generate a daily TIL markdown file and save it to the dev-root-affinity repository if present."""
    import os
    from datetime import datetime
    
    # Determine dev-root-affinity path
    # If we are running in local dev-root-affinity folder directly or side-by-side
    parent_dir = os.path.abspath(os.path.join(os.getcwd(), ".."))
    dev_root_path = os.path.join(parent_dir, "dev-root-affinity")
    notes_dir = os.path.join(dev_root_path, "notes")
    
    if not os.path.exists(notes_dir):
        logger.info("dev-root-affinity repository not found at %s. Skipping daily TIL generation.", dev_root_path)
        return
        
    logger.info("Found dev-root-affinity notes directory at %s. Generating daily TIL...", notes_dir)
    
    # 1. Call Gemini to generate TIL content
    from app.services.llm_service import call_llm_with_fallback
    
    prompt = """You are a highly skilled software engineer writing a "Today I Learned" (TIL) note.
Generate a high-quality markdown TIL note about one interesting, advanced concept in software engineering, cloud systems, databases, machine learning, or Python development.

The note MUST be in this exact format:
# [Topic Name]

[A brief, clear 2-3 sentence explanation of the concept and why it matters.]

## Key Takeaways
- [Takeaway 1]
- [Takeaway 2]
- [Takeaway 3]

## Code Example
[Provide a clear, brief, high-quality code snippet (in Python, SQL, shell, etc.) demonstrating this concept in action.]

---
*Logged on YYYY-MM-DD HH:MM:SS (UTC)*

Replace YYYY-MM-DD HH:MM:SS with the current UTC date and time.
Write only the markdown content, nothing else. Do not wrap it in ```markdown blocks.
Make the concept feel genuine, practical, and highly technical.
"""
    try:
        messages = [
            {"role": "system", "content": "You are a professional software engineering educator."},
            {"role": "user", "content": prompt}
        ]
        content = await call_llm_with_fallback(messages, settings, temperature=0.7)
        if not content:
            logger.error("Generated TIL content is empty.")
            return
            
        # Clean markdown wrappers if present
        content_lines = content.strip().split("\n")
        if content_lines[0].startswith("```"):
            content_lines = content_lines[1:]
        if content_lines[-1].startswith("```"):
            content_lines = content_lines[:-1]
        cleaned_content = "\n".join(content_lines).strip()
        
        # 2. Write the file
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        
        # Create a URL-safe filename from the topic name (first line of cleaned_content)
        first_line = cleaned_content.split("\n")[0]
        topic_title = first_line.replace("#", "").strip().lower()
        safe_title = "".join(c if c.isalnum() or c in (" ", "-", "_") else "" for c in topic_title)
        safe_title = safe_title.replace(" ", "-").replace("--", "-").strip("-")
        
        if not safe_title:
            safe_title = "daily-learning"
            
        filename = f"til-{today_str}-{safe_title}.md"
        file_path = os.path.join(notes_dir, filename)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(cleaned_content + "\n")
            
        logger.info("Successfully wrote daily TIL note to %s", file_path)
    except Exception as exc:
        logger.exception("Failed to generate or save daily TIL note: %s", exc)


async def check_linkedin_token(access_token: str) -> tuple[bool, str]:
    """Ask LinkedIn whether the token still works. The token stored for the pipeline is given a made-up 60-day expiry, so without this
    an expired token only shows up when an approved post fails to publish. Only a 401 counts as expired; anything else is reported and
    the run carries on, so a LinkedIn hiccup does not stop a draft."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get("https://api.linkedin.com/v2/userinfo", headers={"Authorization": f"Bearer {access_token}"})
    except Exception as exc:
        return True, f"not checked ({exc})"
    if resp.status_code == 401:
        return False, "expired or revoked (401)"
    if resp.status_code == 200:
        return True, "valid"
    return True, f"not confirmed ({resp.status_code})"


PENDING_DIR = "pending_post"
# An approval that arrives later than this would post stale news, so the publish step refuses it.
MAX_DRAFT_AGE_HOURS = 36


def _set_output(name: str, value: str):
    path = os.getenv("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")


def _write_pending(result: dict):
    """Save the approved-to-be draft for the publish job, and show it on the run page so it can be read before approving."""
    import json
    import shutil

    os.makedirs(PENDING_DIR, exist_ok=True)
    with open(os.path.join(PENDING_DIR, "post.txt"), "w", encoding="utf-8") as f:
        f.write(result["draft"])
    image = result.get("image_path")
    if image and os.path.exists(image):
        shutil.copy(image, os.path.join(PENDING_DIR, "image.png"))
        os.remove(image)
    meta = {
        "created_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        "format": result.get("format"),
        "subject": result.get("subject"),
        "warnings": result.get("compliance", {}).get("issues", []),
        "alt_text": result.get("alt_text"),
        "visual": result.get("visual"),
        "history_entry": result.get("history_entry"),
    }
    with open(os.path.join(PENDING_DIR, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        warnings = "".join(f"- {w}\n" for w in meta["warnings"]) or "- none\n"
        with open(summary, "a", encoding="utf-8") as f:
            f.write(
                f"## LinkedIn draft waiting for approval\n\n"
                f"Format: {meta['format']} | Subject: {meta['subject']} | {len(result['draft'].split())} words\n\n"
                f"Warnings:\n{warnings}\n"
                f"Approve the **publish** job to post it exactly as below, or reject it to skip today. "
                f"The graphic is in the `pending-post` artifact. Drafts older than {MAX_DRAFT_AGE_HOURS} hours are not posted.\n\n"
                f"```text\n{result['draft']}\n```\n"
            )


async def _seed_user(access_token: str, raw_sub: str, settings) -> int:
    encrypted_token = OAuthToken.encrypt_token(access_token, settings.fernet_key)
    async with async_session() as session:
        from sqlalchemy import delete, select

        res = await session.execute(select(User).where(User.linkedin_sub == raw_sub))
        user = res.scalars().first()
        if user is None:
            user = User(linkedin_sub=raw_sub, name="GitHub Actions Publisher", email="actions@github.local")
            session.add(user)
            await session.flush()
        else:
            logger.info("Found existing user in database, reusing user record.")

        await session.execute(delete(OAuthToken).where(OAuthToken.user_id == user.id))
        session.add(
            OAuthToken(
                user_id=user.id,
                encrypted_access_token=encrypted_token,
                token_type="Bearer",
                expires_at=datetime.utcnow() + timedelta(days=60),
                scopes="openid profile email w_member_social",
            )
        )
        await session.commit()
        logger.info("Database seeded with user (ID: %d) & encrypted token.", user.id)
        return user.id


async def run_draft(user_id: int, settings, token_ok: bool = True):
    """Scheduled step: draft today's post (if one is scheduled) and write the TIL note. Never publishes."""
    if not token_ok:
        # Nothing approved today could be posted, so no draft is offered; the TIL note is still written and the run fails so GitHub emails.
        write_run_log({"status": "failed", "steps": {"linkedin_token": "expired or revoked; renew LINKEDIN_ACCESS_TOKEN"}})
        _set_output("has_draft", "false")
        await generate_and_save_til(settings)
        logger.error("LinkedIn token is expired or revoked. Renew the LINKEDIN_ACCESS_TOKEN secret.")
        sys.exit(1)
        return
    result = await run_daily_pipeline(user_id=user_id, run_type="github_actions_cron")
    write_run_log(result)
    if result.get("status") == "drafted":
        _write_pending(result)
        _set_output("has_draft", "true")
    else:
        _set_output("has_draft", "false")

    await generate_and_save_til(settings)

    if result.get("status") in ("drafted", "skipped"):
        logger.info("Draft step finished: %s", result.get("status"))
        sys.exit(0)
        return
    logger.error("Draft step failed! Error: %s", result.get("error"))
    logger.error("Pipeline steps detail: %s", result.get("steps"))
    sys.exit(1)


async def run_publish(access_token: str, raw_sub: str, settings):
    """Approved step: post the saved draft exactly as it was shown for approval."""
    import json

    from app.services.linkedin_service import publish_post

    text_path, meta_path = os.path.join(PENDING_DIR, "post.txt"), os.path.join(PENDING_DIR, "meta.json")
    if not (os.path.exists(text_path) and os.path.exists(meta_path)):
        logger.error("No pending draft found in %s", PENDING_DIR)
        sys.exit(1)
        return
    with open(text_path, encoding="utf-8") as f:
        text = f.read()
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)

    age = datetime.now(timezone.utc).replace(tzinfo=None) - datetime.fromisoformat(meta["created_at"])
    if age > timedelta(hours=MAX_DRAFT_AGE_HOURS):
        write_run_log({"status": "skipped", "steps": {"publish": f"draft is {age} old, not posted"}})
        logger.warning("Draft is %s old; not posting stale content.", age)
        sys.exit(0)
        return

    image = os.path.join(PENDING_DIR, "image.png")
    result = await publish_post(access_token, f"urn:li:person:{raw_sub}", text, settings, image if os.path.exists(image) else None,
                                meta.get("alt_text"))
    status = "success" if result.get("success") else "failed"
    if status == "success" and meta.get("history_entry"):
        from app.services.post_plan import append_history

        append_history(meta["history_entry"])
    write_run_log({"status": status, "steps": {"publish": "approved and posted" if status == "success" else f"failed: {result.get('error', '')}",
                                               "format": meta.get("format"), "subject": meta.get("subject")}})
    sys.exit(0 if status == "success" else 1)


async def main(mode: str = "draft"):
    logger.info("Initializing GitHub Actions job (%s)", mode)

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
    if mode == "draft" and not openai_api_key:
        logger.error("OPENAI_API_KEY environment variable is not set!")
        sys.exit(1)
        return

    raw_sub = sub_urn.replace("urn:li:person:", "")
    settings = get_settings()

    token_ok, token_state = await check_linkedin_token(access_token)
    logger.info("LinkedIn token: %s", token_state)

    if mode == "publish":
        if not token_ok:
            write_run_log({"status": "failed", "steps": {"publish": "LinkedIn token expired or revoked; renew LINKEDIN_ACCESS_TOKEN"}})
            sys.exit(1)
            return
        await run_publish(access_token, raw_sub, settings)
        return

    await init_db()
    try:
        user_id = await _seed_user(access_token, raw_sub, settings)
    except Exception:
        logger.exception("Failed to encrypt access token using Fernet key!")
        sys.exit(1)
        return
    await run_draft(user_id, settings, token_ok)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "draft"))
