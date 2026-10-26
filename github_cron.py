"""Standalone GitHub Actions runner.

`python -m github_cron draft` (daily): on Mon/Wed/Fri posts the next post the owner approved, word for word; then drafts a new post for
the next open post day, saves it to pending_post/ for approval, and writes the TIL note.
`python -m github_cron approve` (runs only after the owner approves the draft in GitHub): adds it to the approved queue for its post day,
and posts it at once if that day is today.
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


def _set_output(name: str, value: str):
    path = os.getenv("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")


def _write_pending(result: dict, preview: bool = False):
    """Save the approved-to-be draft for the publish job, and show it on the run page so it can be read before approving."""
    import json
    import shutil

    os.makedirs(PENDING_DIR, exist_ok=True)
    with open(os.path.join(PENDING_DIR, "post.txt"), "w", encoding="utf-8") as f:
        f.write(result["draft"])
    pages = [p for p in result.get("document_pages") or [] if os.path.exists(p)]
    if result.get("document_path") and os.path.exists(result["document_path"]) and pages:
        shutil.copy(result["document_path"], os.path.join(PENDING_DIR, "document.pdf"))
        os.makedirs(os.path.join(PENDING_DIR, "pages"), exist_ok=True)
        for n, page in enumerate(pages, 1):
            shutil.copy(page, os.path.join(PENDING_DIR, "pages", f"page-{n}.png"))
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
        "post_day": result.get("post_day"),
        "story_id": (result.get("history_entry") or {}).get("story_id"),
        "document_title": result.get("document_title"),
        "pages": len(os.listdir(os.path.join(PENDING_DIR, "pages"))) if os.path.isdir(os.path.join(PENDING_DIR, "pages")) else 0,
    }
    with open(os.path.join(PENDING_DIR, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        repo, run_id = os.getenv("GITHUB_REPOSITORY", ""), os.getenv("GITHUB_RUN_ID", "")
        # The workflow pushes the image to the previews branch under this name, so the run page can show it inline.
        image_url = (f"https://raw.githubusercontent.com/{repo}/previews/{run_id}.png"
                     if repo and run_id and os.path.exists(os.path.join(PENDING_DIR, "image.png")) else None)
        run_url = f"https://github.com/{repo}/actions/runs/{run_id}" if repo and run_id else ""
        page_urls = [f"https://raw.githubusercontent.com/{repo}/previews/{run_id}-p{n}.png"
                     for n in range(1, meta["pages"] + 1)] if repo and run_id and meta["pages"] else []
        with open(summary, "a", encoding="utf-8") as f:
            f.write(review_summary(result["draft"], meta, image_url, run_url, preview, page_urls))


def _as_markdown_text(text: str) -> str:
    """Show the post as it reads on LinkedIn: paragraphs and "- " lists stay, but nothing else is taken as formatting
    (a line starting with a hashtag would otherwise become a heading)."""
    out = []
    for line in text.splitlines():
        line = line.replace("\\", "\\\\")
        for ch in "*_`<>[]|":
            line = line.replace(ch, "\\" + ch)
        if line.startswith("#"):
            line = "\\" + line
        out.append(line + "  " if line else "")
    return "\n".join(out)


def review_summary(text: str, meta: dict, image_url: str | None, run_url: str, preview: bool = False,
                   page_urls: list[str] | None = None) -> str:
    warnings = meta.get("warnings") or []
    day_label = "its post day"
    if meta.get("post_day"):
        from datetime import date as _date

        d = _date.fromisoformat(meta["post_day"])
        day_label = f"{d:%A, %B} {d.day}"
    if preview:
        head = [
            "# Preview of a new draft: this will not be posted\n",
            f"**{meta.get('format')}** · **{meta.get('subject')}** · {len(text.split())} words · {len(text)} characters\n",
            "A real post day shows this same page, with these steps to approve:\n",
        ]
    else:
        head = [
            "# LinkedIn post ready for your review\n",
            f"**For {day_label}** · {meta.get('subject')} · {len(text.split())} words · {len(text)} characters\n",
            "## How to approve it\n",
        ]
    parts = head + [
        f"1. Read the post and look at the image below.\n"
        f"2. Scroll to the top of {'[this run](' + run_url + ')' if run_url else 'this page'} and click **Review deployments**.\n"
        f"3. Tick **linkedin-publish**, then click **Approve and deploy**. It is posted exactly as shown on {day_label}.\n"
        f"4. Or click **Reject**, and type in the comment box what is wrong (for example \"too many numbers\" or \"wrong focus\"). A new "
        f"draft for the same day is written and sent to you, and your comment is given to it and to every later draft. This repeats "
        f"until one is approved or the day's free AI quota runs out (drafting then carries on with the next day's run).\n",
    ]
    if warnings:
        parts.append("**Check before approving:** " + "; ".join(warnings) + "\n")
    parts.append("---\n\n## The post\n\n" + _as_markdown_text(text) + "\n")
    if page_urls:
        parts.append(f"## The document ({len(page_urls)} pages, posted as a swipeable carousel)\n\n**{meta.get('document_title')}**\n")
        parts += [f"Page {n}\n\n![Page {n}]({u})\n" for n, u in enumerate(page_urls, 1)]
    elif image_url:
        # Markdown image syntax: the run summary drops a raw <img> tag.
        parts.append(f"## The image\n\n![Post image]({image_url})\n\n[Open the image full size]({image_url})\n")
    else:
        parts.append("## The image\n\nNo image with this post.\n")
    if meta.get("alt_text"):
        parts.append(f"**Image description (alt text):** {_as_markdown_text(meta['alt_text'])}\n")
    parts.append("<details><summary>Plain text to copy</summary>\n\n```text\n" + text + "\n```\n\n</details>\n")
    return "\n".join(parts)


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


def _queued_history(item: dict) -> dict:
    entry = dict(item.get("history_entry") or {})
    entry.setdefault("format", item.get("format"))
    entry.setdefault("subject", item.get("subject"))
    entry.setdefault("text", item["text"])
    entry["approved_id"] = item["id"]
    return entry


async def publish_due(access_token: str, raw_sub: str, settings) -> str:
    """On a post day with nothing posted yet, post the next approved post word for word. Returns what happened, for the run log."""
    from app.services.approved_queue import image_copy, next_approved
    from app.services.linkedin_service import publish_post
    from app.services.post_plan import append_history, load_history
    from app.services.post_rules import first_words
    from app.services.summarizer_service import post_format_for
    from app.utils.timezone import today_phoenix

    today = today_phoenix()
    history = load_history()
    if post_format_for(today) is None:
        return f"no post on {today:%A}"
    if any(h.get("date") == str(today) for h in history):
        return "already posted today"
    item = next_approved(history)
    if item is None:
        return "nothing approved for today"
    image = image_copy(item)
    document = item.get("document") if item.get("document") and os.path.exists(item["document"]) else None
    try:
        result = await publish_post(access_token, f"urn:li:person:{raw_sub}", item["text"], settings, image, item.get("alt_text"),
                                    document_path=document, document_title=item.get("document_title"))
    finally:
        if image and os.path.exists(image):
            os.remove(image)
    if not result.get("success"):
        return f"failed to post {item['id']}: {result.get('error', '')}"
    entry = _queued_history(item)
    entry["date"] = str(today)
    entry.setdefault("opener_words", first_words(item["text"]))
    append_history(entry)
    return f"posted {item['id']}"


async def run_draft(user_id: int, settings, token_ok: bool = True, access_token: str = "", raw_sub: str = ""):
    """Daily step: post today's approved post if one is due, then draft a post for the next open post day and offer it for approval.
    Drafting pauses while a draft waits for approval or QUEUE_AHEAD approved posts are already waiting."""
    from app.services.approved_queue import QUEUE_AHEAD, slot_for_next_draft, unposted
    from app.services.post_plan import load_history
    from app.services.summarizer_service import post_format_for
    from app.utils.timezone import today_phoenix

    _set_output("has_draft", "false")
    preview = os.getenv("PREVIEW_FORMAT", "").strip()
    if preview and preview != "none":
        # A manual preview: draft a new post of this format to read on the run page. Nothing is offered for approval.
        result = await run_daily_pipeline(user_id=user_id, run_type="preview", draft_format=preview,
                                          extra_history=[_queued_history(i) for i in unposted(load_history())], use_stories=True)
        if result.get("status") == "drafted":
            _write_pending(result, preview=True)
            _set_output("has_preview", "true")
            logger.info("Preview drafted: %s about %s", result.get("format"), result.get("subject"))
            sys.exit(0)
            return
        if result.get("rejected_draft"):
            # Show the draft that failed the rules, with its problems, so the preview still shows what the model wrote.
            _write_pending({"draft": result["rejected_draft"], "format": result.get("format"), "subject": result.get("subject"),
                            "compliance": {"issues": [f"failed the post rules: {p}" for p in result.get("problems", [])]}},
                           preview=True)
            _set_output("has_preview", "true")
        logger.error("Preview not drafted: %s %s", result.get("error") or result.get("reason"), result.get("steps"))
        sys.exit(1)
        return
    redraft = os.getenv("REDRAFT", "").lower() == "true"
    if redraft:
        # The owner's reason for rejecting the last draft: kept in data/feedback.json and given to every later draft. A story rejected
        # twice is not offered again.
        from app.services.story_bank import add_feedback
        from app.utils.timezone import today_phoenix as _today

        comment = os.getenv("REJECT_COMMENT", "").strip()
        rejected_story = os.getenv("REJECTED_STORY", "").strip()
        if comment or rejected_story:
            add_feedback({"date": str(_today()), "story_id": rejected_story or None, "comment": comment})
    if not token_ok:
        # Nothing could be posted, so no draft is offered; the TIL note is still written and the run fails so GitHub emails.
        write_run_log({"status": "failed", "steps": {"linkedin_token": "expired or revoked; renew LINKEDIN_ACCESS_TOKEN"}})
        if not redraft:
            await generate_and_save_til(settings)
        logger.error("LinkedIn token is expired or revoked. Renew the LINKEDIN_ACCESS_TOKEN secret.")
        sys.exit(1)
        return

    steps = {"publish": await publish_due(access_token, raw_sub, settings)}
    publish_failed = steps["publish"].startswith("failed")
    posted = steps["publish"].startswith("posted")

    history = load_history()
    waiting_approval = int(os.getenv("WAITING_APPROVALS", "0") or 0)
    ready = unposted(history)
    result = {"status": "skipped"}
    if waiting_approval:
        steps["draft"] = "a draft is already waiting for approval"
    elif len(ready) >= QUEUE_AHEAD:
        steps["draft"] = f"{len(ready)} approved posts already waiting"
    else:
        day = slot_for_next_draft(today_phoenix(), history)
        fmt = post_format_for(day)
        result = await run_daily_pipeline(user_id=user_id, run_type="redraft" if redraft else "github_actions_cron", draft_format=fmt,
                                          draft_day=day, extra_history=[_queued_history(i) for i in ready], use_stories=True)
        steps["draft"] = f"{fmt} for {day:%a %b} {day.day}"
        steps.update({k: v for k, v in result.get("steps", {}).items() if k not in ("duplicate_check", "token_check")})
        if result.get("status") == "drafted":
            result["post_day"] = str(day)
            _write_pending(result)
            _set_output("has_draft", "true")

    if publish_failed or result.get("status") == "failed":
        status = "failed"
    elif result.get("status") == "drafted":
        status = "drafted"
    else:
        status = "posted" if posted else "skipped"
    write_run_log({"status": status, "steps": steps})

    if not redraft:
        await generate_and_save_til(settings)
    if status == "failed":
        logger.error("Run failed: %s %s", result.get("error"), steps)
        sys.exit(1)
        return
    logger.info("Daily step finished: %s", steps)
    sys.exit(0)


async def run_approve(access_token: str, raw_sub: str, settings):
    """Runs only after the owner approves a draft in GitHub: adds it to the approved queue for its post day, and posts it right away when
    that day is today and nothing has been posted yet."""
    import json
    import shutil

    from app.services.approved_queue import add_to_queue

    text_path, meta_path = os.path.join(PENDING_DIR, "post.txt"), os.path.join(PENDING_DIR, "meta.json")
    if not (os.path.exists(text_path) and os.path.exists(meta_path)):
        logger.error("No pending draft found in %s", PENDING_DIR)
        sys.exit(1)
        return
    with open(text_path, encoding="utf-8") as f:
        text = f.read()
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    item_id = f"draft-{os.getenv('GITHUB_RUN_ID') or datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    image = os.path.join(PENDING_DIR, "image.png")
    image_dst = None
    if os.path.exists(image):
        os.makedirs(os.path.join("assets", "approved"), exist_ok=True)
        image_dst = f"assets/approved/{item_id}.png"
        shutil.copy(image, image_dst)
    document = os.path.join(PENDING_DIR, "document.pdf")
    document_dst = None
    if os.path.exists(document):
        os.makedirs(os.path.join("assets", "approved"), exist_ok=True)
        document_dst = f"assets/approved/{item_id}.pdf"
        shutil.copy(document, document_dst)
    add_to_queue({"id": item_id, "format": meta.get("format"), "subject": meta.get("subject"), "text": text, "image": image_dst,
                  "alt_text": meta.get("alt_text"), "post_day": meta.get("post_day"), "history_entry": meta.get("history_entry"),
                  "document": document_dst, "document_title": meta.get("document_title")})
    steps = {"approved": f"{item_id} ({meta.get('subject')}) for {meta.get('post_day')}"}
    steps["publish"] = await publish_due(access_token, raw_sub, settings)
    failed = steps["publish"].startswith("failed")
    write_run_log({"status": "failed" if failed else "approved", "steps": steps})
    sys.exit(1 if failed else 0)


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

    if mode == "uploadcheck":
        # Uploads a one-page PDF and a PNG to LinkedIn's documents and images APIs and creates no post: proves the token may upload
        # the media a post needs, without publishing anything.
        from app.services.linkedin_service import _upload
        from PIL import Image

        img = Image.new("RGB", (1080, 1350), (17, 19, 21))
        img.save("check.png")
        img.save("check.pdf", "PDF")
        headers = {"Authorization": f"Bearer {access_token}", "LinkedIn-Version": "202605", "X-Restli-Protocol-Version": "2.0.0",
                   "Content-Type": "application/json"}
        doc = await _upload("documents", "check.pdf", f"urn:li:person:{raw_sub}", headers)
        image = await _upload("images", "check.png", f"urn:li:person:{raw_sub}", headers)
        logger.info("Upload check: document %s, image %s (no post created)", doc or "FAILED", image or "FAILED")
        if os.getenv("GROQ_API_KEY"):
            import httpx

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get("https://api.groq.com/openai/v1/models",
                                        headers={"Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}"})
            ids = sorted(m.get("id", "") for m in resp.json().get("data", [])) if resp.status_code == 200 else [f"HTTP {resp.status_code}"]
            logger.info("Groq models available to this key: %s", ", ".join(ids))
        sys.exit(0 if doc and image else 1)
        return

    if mode in ("approve", "publish"):
        if not token_ok:
            write_run_log({"status": "failed", "steps": {"approve": "LinkedIn token expired or revoked; renew LINKEDIN_ACCESS_TOKEN"}})
            sys.exit(1)
            return
        await run_approve(access_token, raw_sub, settings)
        return

    await init_db()
    try:
        user_id = await _seed_user(access_token, raw_sub, settings)
    except Exception:
        logger.exception("Failed to encrypt access token using Fernet key!")
        sys.exit(1)
        return
    await run_draft(user_id, settings, token_ok, access_token, raw_sub)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "draft"))
