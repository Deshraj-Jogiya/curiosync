"""LinkedIn Comment Monitoring & Auto-Response Service (Pointers 4 & 5)."""

import os
import re
import datetime
import urllib.parse
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.post_history import PostHistory
from app.services.llm_service import call_llm_with_fallback
from app.utils.logging import logger

SUPABASE_URL = "https://mtvcrttbdjwcixzhlkvo.supabase.co"
SUPABASE_KEY = "sb_publishable_ZuB30vNfc-7b7Pr6ebZNqQ_sXjox-wu"  # Anon/Publishable Key

SAFE_PROJECT_QUERIES = {
    "/run tax_audit": "Executing simulated Tax Anomaly Audit pipeline run.\nModel: Isolation Forest.\nScope: 1,240 general ledger transactions.\nResults: 42 outliers flagged (3.3% anomaly rate).\nBenford's Law distribution correlation score: 94.6%.\nExecution state: success.",
    "/run clinical_trials": "Executing simulated Clinical Trials Outcomes pipeline run.\nModel: BioBERT NLP Entity Extractor.\nScope: 85 recruiting oncology trials retrieved.\nResults: 14 matching cohort segments identified, eligibility criteria semantic parsing completed.\nExecution state: success.",
    "/run carbon_emissions": "Executing simulated Multi-State Land Use Emissions pipeline run.\nModel: Random Forest Spatial Regressor.\nScope: 5 regional geospatial raster data grids.\nResults: CO2 anomaly detection completed, forest-loss trajectory projection accuracy: 90.2%.\nExecution state: success."
}

async def check_user_daily_limit(author_urn: str) -> bool:
    """Check if the user has reached their daily limit of 2 comment replies in Supabase."""
    today_str = datetime.datetime.utcnow().date().isoformat()
    url = f"{SUPABASE_URL}/rest/v1/linkedin_comments"
    params = {
        "author_urn": f"eq.{author_urn}",
        "processed_at": f"gte.{today_str}T00:00:00Z",
        "select": "comment_id"
    }
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params, headers=headers)
        if resp.status_code == 200:
            comments = resp.json()
            return len(comments) >= 2
        else:
            logger.error("Failed to fetch user limits from Supabase. Status: %d, Response: %s", resp.status_code, resp.text)
            return False
    except Exception as e:
        logger.exception("Error checking user daily limits in Supabase: %s", e)
        return False

async def is_comment_processed(comment_id: str) -> bool:
    """Check if a comment has already been processed and replied to."""
    url = f"{SUPABASE_URL}/rest/v1/linkedin_comments"
    params = {
        "comment_id": f"eq.{comment_id}",
        "select": "comment_id"
    }
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params, headers=headers)
        if resp.status_code == 200:
            return len(resp.json()) > 0
        return False
    except Exception as e:
        logger.exception("Error checking comment processed status in Supabase: %s", e)
        return False

async def save_processed_comment(comment_id: str, post_id: str, author_urn: str, author_name: str, comment_text: str, reply_text: str):
    """Save processed comment record to Supabase to mark it as handled and increment the limit."""
    url = f"{SUPABASE_URL}/rest/v1/linkedin_comments"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    payload = {
        "comment_id": comment_id,
        "post_id": post_id,
        "author_urn": author_urn,
        "author_name": author_name,
        "comment_text": comment_text,
        "reply_text": reply_text
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code not in (200, 201):
            logger.error("Failed to save processed comment to Supabase. Status: %d, Response: %s", resp.status_code, resp.text)
    except Exception as e:
        logger.exception("Error saving processed comment to Supabase: %s", e)

async def generate_chatbot_reply(comment_text: str, settings: Settings) -> str:
    """Generate a career chatbot response using Gemini with strict safety rules."""
    system_prompt = """You are a virtual career assistant chatbot trained on Deshraj Jogiya's professional profile.
Your goal is to answer questions about his technical experience, projects, or background.
You must stay professional, polite, objective, and speak in the third person.
Do not use bullet points, numbered lists, hyphens, dashes, or emojis.
Write in a single, short, warm paragraph of natural storytelling prose (under 60 words).

Deshraj's Background:
- Master's in IT from Arizona State University (4.0 GPA).
- 5 years of experience in data engineering and machine learning.
- Work history: Applied ML Engineer at Technoid LLC, Data Analyst at Zifatech Solutions.
- Projects: FinTech Credit Risk, Multi-State Land Use, IoT Telematics, STEM ASL Recognition, Tax Anomaly Audit.
- Email: djogiya786@gmail.com
- Portfolio: deshraj-jogiya.github.io
"""
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"User comment: {comment_text}"}
    ]
    try:
        reply = await call_llm_with_fallback(messages, settings, temperature=0.5)
        # Enforce no lists/dashes on output text
        reply = reply.replace("-", " ").replace("*", "").replace("•", "")
        # Remove any numbering at start
        reply = re.sub(r'^\d+\.\s*', '', reply)
        return reply
    except Exception as e:
        logger.exception("Error generating chatbot response: %s", e)
        return "Deshraj is a Data Engineer and ML Engineer with a Master's from ASU. You can find more about his projects or contact him directly via email at djogiya786@gmail.com."

async def fetch_and_reply_comments(db: AsyncSession, settings: Settings):
    """Fetch comments on recent posts and reply to them while respecting safety and rates."""
    # Get token for authentication
    from app.models.token import OAuthToken
    from sqlalchemy import select
    
    res = await db.execute(select(OAuthToken).order_by(OAuthToken.id.desc()).limit(1))
    token_rec = res.scalars().first()
    if not token_rec:
        logger.error("No LinkedIn OAuth token found in database. Cannot run comment agent.")
        return

    access_token = token_rec.decrypt_access_token(settings.fernet_key)
    # Get user sub URN to verify we don't reply to ourselves
    from app.models.user import User
    res = await db.execute(select(User).where(User.id == token_rec.user_id))
    user = res.scalars().first()
    if not user:
        logger.error("No user found associated with token.")
        return
        
    my_sub = user.linkedin_sub
    my_urn = f"urn:li:person:{my_sub}"

    # Fetch last 7 days of published posts
    seven_days_ago = datetime.date.today() - datetime.timedelta(days=7)
    res = await db.execute(
        select(PostHistory)
        .where(PostHistory.status == "published", PostHistory.date_for >= seven_days_ago)
        .order_by(PostHistory.id.desc())
    )
    posts = res.scalars().all()
    
    if not posts:
        logger.info("No published posts found in the last 7 days to scan for comments.")
        return

    headers = {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": "202605",
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }

    logger.info("Scanning comments for %d recent posts...", len(posts))

    for post in posts:
        post_urn = post.linkedin_post_id
        if not post_urn:
            continue
            
        if not post_urn.startswith("urn:li:"):
            post_urn = f"urn:li:share:{post_urn}"

        # Fetch comments for this post
        encoded_urn = urllib.parse.quote(post_urn)
        comments_url = f"https://api.linkedin.com/rest/socialActions/{encoded_urn}/comments"
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(comments_url, headers=headers)
                
            if resp.status_code == 403:
                logger.warning("LinkedIn API returned 403 Access Denied. Your app requires the Community Management API product. Skipping comment scanning.")
                return  # Return immediately since token lacks permissions
                
            if resp.status_code != 200:
                logger.error("Failed to fetch comments for post %s. Status: %d, Response: %s", post_urn, resp.status_code, resp.text)
                continue
                
            comments_data = resp.json()
            elements = comments_data.get("elements", [])
            
            for element in elements:
                comment_id = element.get("id")
                actor = element.get("created", {}).get("actor")
                comment_text = element.get("message", {}).get("text", "").strip()
                
                if not comment_id or not actor or not comment_text:
                    continue
                    
                # Skip if comment is by the bot itself
                if actor == my_urn:
                    continue
                    
                # Check if already processed
                if await is_comment_processed(comment_id):
                    continue
                    
                logger.info("New comment detected: ID=%s, Actor=%s, Content=%s", comment_id, actor, comment_text)
                
                # Check rate limit
                if await check_user_daily_limit(actor):
                    logger.info("Actor %s has reached their daily reply limit. Sending rate limit warning.", actor)
                    reply_text = "Thank you for connecting! To protect API limits, automated replies are capped at two per day per user. Please visit the live portfolio at deshraj-jogiya.github.io to play with the SQL sandbox and chatbot without limits!"
                else:
                    # Determine comment type and reply content
                    # Case 1: Pre-defined SQL queries
                    command = comment_text.lower().strip()
                    if command in SAFE_PROJECT_QUERIES:
                        reply_text = SAFE_PROJECT_QUERIES[command]
                    # Case 2: Generic career inquiries
                    else:
                        reply_text = await generate_chatbot_reply(comment_text, settings)
                
                # Post the reply comment
                reply_payload = {
                    "actor": my_urn,
                    "message": {
                        "text": reply_text
                    },
                    "parentComment": comment_id
                }
                
                reply_url = f"https://api.linkedin.com/rest/socialActions/{encoded_urn}/comments"
                async with httpx.AsyncClient() as client:
                    reply_resp = await client.post(reply_url, json=reply_payload, headers=headers)
                    
                if reply_resp.status_code in (200, 201):
                    logger.info("Successfully posted automated reply to LinkedIn.")
                    # Record in Supabase
                    await save_processed_comment(
                        comment_id=comment_id,
                        post_id=post_urn,
                        author_urn=actor,
                        author_name=actor.split(":")[-1],
                        comment_text=comment_text,
                        reply_text=reply_text
                    )
                else:
                    logger.error("Failed to post reply to LinkedIn. Status: %d, Response: %s", reply_resp.status_code, reply_resp.text)
                    
        except Exception as e:
            logger.exception("Error processing comments for post %s: %s", post_urn, e)
