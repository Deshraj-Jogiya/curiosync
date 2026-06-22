"""Draft generation service using OpenAI / Gemini with resume personalization."""

import json
import os
import random
import openai

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.config import Settings
from app.models.showcased_project import ShowcasedProject
from app.services.resume_service import RESUME_DATA, get_resume_context
from app.services.llm_service import call_llm_with_fallback
from app.utils.logging import logger

PERSONALIZED_POST_PROMPT = """\
You are a Senior Data & AI/ML Engineer. Write one highly engaging, human-written, and technically detailed LinkedIn post based on today's tech news.

Your writing style must match the following storytelling engineering reference style (natural, reflective, conversational but professional, sharing personal hands-on experience and insights):

=== REFERENCE STYLE ===
Many engineering teams treat database synchronization as an afterthought—until latency spikes and client sessions start dropping. When building real-time recommendation engines, we saw how critical synchronizing PostgreSQL and Supabase is for scaling operations. By structuring Row-Level Security correctly and optimizing the transaction replication lag, we cut backend synchronization latency by 65%. Today's news about AI governance highlights the same fundamental truth: you cannot build reliable intelligent workflows on top of a fragmented data layer. Factual, robust validation isn't optional. Check out these live pipeline widgets and test my interactive SQL sandbox at deshraj-jogiya.github.io #DataEngineering #MachineLearning
=== END REFERENCE STYLE ===

Your profile and context:
{resume_context}

Rules:
- Write exactly 120 to 180 words total. Do NOT exceed 180 words.
- Write in a flowing narrative, storytelling paragraph style. Do NOT use headings (like "Executive Summary"), do NOT use numbered sections, and do NOT use bullet points.
- Maintain a calm, authoritative, reflective tone. Do NOT use sensational hype or generic clickbait phrases (e.g. "Let's dive in", "In today's fast-paced world").
- Relate your own professional experiences (e.g., ETL pipelines, model optimizations, star schemas) from your profile context to the theme of today's tech news.
- The post MUST conclude with a brief, organic call to action inviting people to play with your interactive widgets and test your live SQL sandbox at deshraj-jogiya.github.io
- Use plain, active English with a professional developer voice.
- Do NOT use any emojis.
- Use ONLY the provided news items as source material.
- Add exactly 2-3 relevant technical hashtags at the very end.
- Return ONLY the final post text, nothing else.

Today's top tech news:
{news_items}"""

LINKEDIN_POST_PROMPT = PERSONALIZED_POST_PROMPT

MONDAY_SPOTLIGHT_PROMPT = """\
You are a Senior Data & AI/ML Engineer. Write one highly engaging, human-written LinkedIn post spotlighting one of your technical projects in a reflective, storytelling style to demonstrate real-world domain expertise.

Your writing style must match the following storytelling engineering reference style (conversational, professional, highlighting technical problems, implementation details, and business impact):

=== REFERENCE STYLE ===
A few months ago, I was debugging a latency issue in our microservice analytics sync. Fragmented reporting was causing data discrepancies and delayed dashboards. To solve this, I transformed our SQL-based ETL pipelines, automating the daily transactional data ingestion. By normalizing the data streams and migrating workflows to AWS Glue, we cut manual data reporting effort by 70% and boosted Snowflake warehouse data availability by 60%. Having Great Expectations run quality checks meant we secured a 98% data reliability standard. If you want to discuss scalable databases or check out my live project demos, visit my portfolio at deshraj-jogiya.github.io #DataAutomation #CloudMigration
=== END REFERENCE STYLE ===

User Profile & Resume:
{resume_context}

Project Details:
{project_info}

Rules:
- Write exactly 120 to 180 words total. Do NOT exceed 180 words.
- Write in a natural, storytelling paragraph style. Do NOT use headings, numbered sections, or bullet points.
- Focus on the concrete technical problem, your engineering implementation, and the quantitative impact (e.g., latency reductions, accuracy gains, automation percentage).
- The post MUST end with a professional closing inviting technical leaders to connect, read more, or test live project widgets at deshraj-jogiya.github.io
- Use plain, active English. Do NOT use emojis.
- Add exactly 2-3 relevant technical hashtags at the very end.
- Return ONLY the final post text, nothing else.
"""



def _format_news_for_prompt(news_items: list[dict]) -> str:
    """Format news items into a numbered list for the prompt."""
    lines: list[str] = []
    for i, item in enumerate(news_items, 1):
        summary = item.get("summary", "")
        source = item.get("source_name", "")
        lines.append(f"{i}. [{source}] {item['title']}")
        if summary:
            lines.append(f"   {summary[:200]}")
    return "\n".join(lines)


async def generate_draft(news_items: list[dict], settings: Settings) -> str:
    """Generate a personalized LinkedIn post draft from today's news."""
    formatted = _format_news_for_prompt(news_items)
    resume_context = get_resume_context()
    prompt = PERSONALIZED_POST_PROMPT.format(
        resume_context=resume_context, news_items=formatted
    )

    logger.info(
        "Generating draft via LLM",
        extra={"model": settings.openai_model, "news_count": len(news_items)},
    )

    text = await call_llm_with_fallback(
        messages=[{"role": "user", "content": prompt}],
        settings=settings,
        temperature=0.7,
    )
    logger.info(
        "Draft generated",
        extra={"word_count": len(text.split()), "char_count": len(text)},
    )
    return text


async def generate_monday_project_spotlight(
    projects: list[dict], settings: Settings, db: AsyncSession = None
) -> str:
    """Generate a LinkedIn post spotlighting one project from GitHub or Resume."""
    resume_context = get_resume_context()

    selected = None
    project_type = "github" if projects else "resume"

    if not projects:
        projects = RESUME_DATA.get("projects", [])

    if projects:
        # If database session is provided, implement stateful rotation
        if db is not None:
            try:
                JSON_BACKUP_PATH = "showcased_projects.json"

                # 1. Seed the database from JSON file if the DB table is empty
                # Check if DB table is empty
                stmt = select(ShowcasedProject)
                result = await db.execute(stmt)
                db_records = result.scalars().all()

                if not db_records and os.path.exists(JSON_BACKUP_PATH):
                    try:
                        with open(JSON_BACKUP_PATH, "r", encoding="utf-8") as f:
                            saved_names = json.load(f)
                        if isinstance(saved_names, list):
                            for name in saved_names:
                                db.add(ShowcasedProject(project_name=name, project_type=project_type))
                            await db.commit()
                    except Exception as json_err:
                        logger.error("Failed to seed database from JSON backup file: %s", json_err)

                # 2. Query showcased projects from database (now seeded if backup existed)
                stmt = select(ShowcasedProject.project_name)
                result = await db.execute(stmt)
                showcased_names = set(result.scalars().all())

                # 3. Filter unshowcased projects
                unshowcased = [p for p in projects if p.get("name") not in showcased_names]

                if not unshowcased:
                    # 4. All projects have been showcased! Reset history.
                    # Find the most recently showcased project to avoid back-to-back repeats
                    last_stmt = select(ShowcasedProject.project_name).order_by(ShowcasedProject.showcased_at.desc()).limit(1)
                    last_result = await db.execute(last_stmt)
                    last_showcased = last_result.scalar_one_or_none()

                    # Reset/delete all records in the table
                    await db.execute(delete(ShowcasedProject))
                    await db.commit()

                    # Exclude the last showcased project from the immediate choice if we have other options
                    pool = [p for p in projects if p.get("name") != last_showcased]
                    if not pool:
                        pool = projects  # Fallback if only 1 project exists overall
                    
                    # For GitHub projects, maintain star order (pool[0]); for resume projects, pick pool[0]
                    selected = pool[0]
                    logger.info(
                        "Showcase cycle reset",
                        extra={"last_showcased": last_showcased, "new_choice": selected.get("name")}
                    )
                else:
                    # Pick the next unshowcased project
                    # Since projects is already sorted (GitHub repos by stars), unshowcased[0] picks the next highest priority
                    selected = unshowcased[0]

                # 5. Mark the selected project as showcased
                if selected:
                    new_showcase = ShowcasedProject(
                        project_name=selected.get("name"),
                        project_type=project_type
                    )
                    db.add(new_showcase)
                    await db.commit()

                # 6. Export updated showcase list to JSON backup file
                all_stmt = select(ShowcasedProject.project_name)
                all_result = await db.execute(all_stmt)
                updated_names = all_result.scalars().all()
                try:
                    with open(JSON_BACKUP_PATH, "w", encoding="utf-8") as f:
                        json.dump(updated_names, f, indent=2)
                except Exception as json_err:
                    logger.error("Failed to write to JSON backup file: %s", json_err)

            except Exception as e:
                logger.exception("Error during stateful project rotation. Falling back to random selection.", extra={"error": str(e)})
                # Fallback to stateless logic in case of database errors
                selected = None

        # If database is not provided, or if selection failed, fallback to stateless logic
        if not selected:
            if project_type == "github":
                # Select randomly from top 3 if available to rotate, or just first
                selected = random.choice(projects[:3]) if len(projects) >= 3 else projects[0]
            else:
                selected = random.choice(projects) if projects else None

    # Format project_info for prompt
    if selected:
        if project_type == "github":
            project_info = (
                f"Repository Name: {selected.get('name')}\n"
                f"GitHub URL: {selected.get('html_url')}\n"
                f"Description: {selected.get('description') or 'No description'}\n"
                f"Primary Language: {selected.get('language') or 'Unknown'}\n"
                f"Topics: {', '.join(selected.get('topics', []))}"
            )
        else:
            project_info = (
                f"Project Name: {selected.get('name')}\n"
                f"Dates: {selected.get('dates')}\n"
                f"Accomplishments:\n"
                + "\n".join(f"- {a}" for a in selected.get("accomplishments", []))
            )
    else:
        project_info = "No specific project details available. Write a general spotlight post about learning data pipeline engineering."


    prompt = MONDAY_SPOTLIGHT_PROMPT.format(
        resume_context=resume_context, project_info=project_info
    )

    logger.info(
        "Generating Monday Project Spotlight via LLM",
        extra={"model": settings.openai_model},
    )

    text = await call_llm_with_fallback(
        messages=[{"role": "user", "content": prompt}],
        settings=settings,
        temperature=0.7,
    )
    logger.info(
        "Monday Spotlight generated",
        extra={"word_count": len(text.split()), "char_count": len(text)},
    )
    return text


def validate_draft_length(text: str) -> tuple[bool, int]:
    """Check whether the draft falls within the 120–180 word target range."""
    word_count = len(text.split())
    valid = 120 <= word_count <= 180
    return valid, word_count
