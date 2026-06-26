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

Your writing style must match the following storytelling engineering structure:

=== REQUIRED STRUCTURE ===
1. A brief summary of the top worthy technical news (covering Tech, Data, AI-ML, Robotics, or other fields related to your work profile) formatted as 2-3 clean, easy-to-read bulleted pointers. Do NOT use any emojis, hyphens as bullet points (use standard unicode bullet points like •), or unicode styling like bold text (e.g. 𝘁𝗵𝗶𝘀).
2. A transition to a storytelling section that connects this news to your own work (referencing your Arizona State University Master's degree, 4.0 GPA, and 5 years of experience in data engineering/ML). Clearly establish a direct connection: what you built (e.g. ETL pipelines, model optimizations, databases), what you achieved (e.g. latency reductions, accuracy gains), and how that makes sense in the context of the real-world news developments.
3. A transparent pipeline statement: "This post was fully compiled and published by my automated, self-hosted serverless data pipeline project."
4. A Call to Action inviting readers to visit your live portfolio and interact with the SQL sandbox and chatbot assistant at deshraj-jogiya.github.io
5. A professional closing asking about available job opportunities and inviting recruiters/hiring managers to connect.
=== END REQUIRED STRUCTURE ===

=== REFERENCE POST TEMPLATE ===
Today's top developments in AI and data engineering highlight two major updates:
• OpenAI released new guidelines for real-time model evaluations to measure latency under load.
• NVIDIA announced hardware-level optimizations for vector storage clusters to reduce retrieval times.

Seeing these advancements in model efficiency reminds me of my time building machine learning recommendation workflows. In my work optimizing LLM processing pipelines, I focused heavily on backend latency, restructuring PostgreSQL and Supabase synchronization layers to cut synchronization delay by 65%. In a world where real-time evaluation is crucial, having highly reliable, synchronized data replication is the foundation of any scalable AI system.

This post was fully compiled and published by my automated, self-hosted serverless data pipeline project. I invite you to visit my live portfolio at deshraj-jogiya.github.io to test my interactive SQL sandbox and query my career chatbot directly. I am currently seeking new opportunities as a Data Engineer or ML Engineer and would love to connect with engineering leaders and hiring teams. #DataEngineering #MachineLearning
=== END REFERENCE POST TEMPLATE ===

Your profile and context:
{resume_context}

Rules:
- Write in a natural, storytelling voice using short paragraphs (2-4 sentences each) separated by double line breaks for readability.
- Write exactly 180 to 280 words total. Do NOT exceed 280 words.
- Do NOT use emojis.
- Do NOT use special/alien characters (e.g. bold unicode text). Use standard plain text only.
- Keep the length decent to keep viewers engaged throughout without being overly verbose or ambiguous.
- Use ONLY the provided news items as source material.
- Add exactly 2-3 relevant technical hashtags at the very end.
- Return ONLY the final post text, nothing else.

Today's top tech news:
{news_items}
"""

LINKEDIN_POST_PROMPT = PERSONALIZED_POST_PROMPT

MONDAY_SPOTLIGHT_PROMPT = """\
You are a Senior Data & AI/ML Engineer. Write one highly engaging, human-written LinkedIn post spotlighting one of your technical projects in a reflective, storytelling style.

Your writing style must match the following storytelling engineering structure:

=== REQUIRED STRUCTURE ===
1. A brief hook and summary of the engineering context or industry relevance of the project formatted as 2-3 easy-to-read bulleted pointers (using •). Do NOT use emojis or bold unicode text.
2. A storytelling section highlighting the concrete technical problem you tackled, your implementation details (referencing your Arizona State University IT Master's, 4.0 GPA, or 5 years of experience), and the quantitative achievements or results (e.g., latency cuts, accuracy improvements).
3. A transparent pipeline statement: "This post was fully compiled and published by my automated, self-hosted serverless data pipeline project."
4. A Call to Action inviting readers to visit your live portfolio and interact with the SQL sandbox and chatbot assistant at deshraj-jogiya.github.io
5. A professional closing asking about available job opportunities and inviting recruiters/hiring managers to connect.
=== END REQUIRED STRUCTURE ===

=== REFERENCE POST TEMPLATE ===
Managing geospatial data in environmental analytics comes with unique challenges:
• Land cover datasets are fragmented across multiple states, causing severe processing bottlenecks.
• High latency in raster transformations delays downstream carbon emission forecasting.

To solve this, I engineered a Python ETL pipeline to automate the ingestion and geospatial transformation of massive datasets into a centralized SQL database. By integrating Linear Regression and Random Forest models, we began forecasting carbon trends based on land-use changes with a 90% forecasting accuracy, saving 10 engineering hours weekly. In production, this showed how critical robust pipelines are for turning raw spatial data into rapid, actionable insights.

This post was fully compiled and published by my automated, self-hosted serverless data pipeline project. I invite you to visit my live portfolio at deshraj-jogiya.github.io to test my interactive SQL sandbox and query my career chatbot directly. I am currently seeking new opportunities as a Data Engineer or ML Engineer and would love to connect with engineering leaders and hiring teams. #DataEngineering #MachineLearning
=== END REFERENCE POST TEMPLATE ===

User Profile & Resume:
{resume_context}

Project Details:
{project_info}

Rules:
- Write in a natural, storytelling voice using short paragraphs separated by double line breaks.
- Write exactly 180 to 280 words total. Do NOT exceed 280 words.
- Do NOT use emojis.
- Do NOT use special/alien characters (e.g. bold unicode text). Use standard plain text only.
- Keep the length decent to keep viewers engaged.
- Add exactly 2-3 relevant technical hashtags at the very end.
- Return ONLY the final post text, nothing else.
"""
""



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
    """Check whether the draft falls within the 150–300 word target range."""
    word_count = len(text.split())
    valid = 150 <= word_count <= 300
    return valid, word_count
