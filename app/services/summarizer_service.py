"""Draft generation service using OpenAI / Gemini with resume personalization."""

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
You are an executive-level Data & AI/ML Engineer. Write one highly structured, professional LinkedIn post based on today's tech news.

Your writing style must match the following reference style (direct, objective, clear, professional, and structured):

=== REFERENCE STYLE ===
Enterprise Data Consolidation and Intelligence Framework
1. Executive Summary
The organization operates a large-scale Event and Talent Management Enterprise, responsible for coordinating artists, events, presenters, agents, and financial operations across multiple regions. Over time, operational complexity and fragmented data systems have led to inefficiencies in financial management, performance tracking, and strategic decision-making.
This project aims to design and implement a comprehensive Enterprise Data Consolidation and Intelligence Framework that integrates all operational data into a unified, normalized, and analytics-ready architecture.
=== END REFERENCE STYLE ===

Your profile and context:
{resume_context}

Rules:
- Write exactly 120 to 180 words total. Do NOT exceed 180 words.
- Maintain a calm, objective, executive-report tone. Do NOT use sensational language, hype, dramatic words (e.g., "vaporize", "dead", "fault line"), or clickbait hooks.
- Do NOT start the post with a question. Start with a direct, professional statement of fact or analysis.
- Do NOT use rhetorical or engagement-bait questions at the beginning or end of the post. The closing must be a professional, objective statement of analysis or strategic implication.
- Write from the perspective of an executive Data & ML practitioner, linking your professional experience (e.g., ETL automation, AI model optimization, data pipelines) to today's news where relevant.
- Structure the post with:
  1. A strong, professional opening theme sentence.
  2. 3 to 4 technical bullet points summarizing key news developments (focus on AI governance, data engineering, model reliability, and tech infrastructure). Keep them clear, simple, and factual.
  3. A concise closing insight or strategic outlook (statement only, no questions).
  4. Exactly 2-4 professional hashtags (e.g., #DataEngineering, #MachineLearning).
- Use plain, active English with executive tone.
- Do NOT use any emojis except plain bullet points (e.g., * or -).
- Use ONLY the provided news items as source material.
- Return ONLY the final post text, nothing else.

Today's top tech news:
{news_items}"""

LINKEDIN_POST_PROMPT = PERSONALIZED_POST_PROMPT

MONDAY_SPOTLIGHT_PROMPT = """\
You are an executive-level Data & AI/ML Engineer. Write one highly structured, professional LinkedIn post spotlighting one of your technical projects to attract recruiters and demonstrate domain expertise.

Your writing style must match the following reference style (direct, objective, clear, professional, and structured):

=== REFERENCE STYLE ===
Enterprise Data Consolidation and Intelligence Framework
1. Executive Summary
The organization operates a large-scale Event and Talent Management Enterprise, responsible for coordinating artists, events, presenters, agents, and financial operations across multiple regions. Over time, operational complexity and fragmented data systems have led to inefficiencies in financial management, performance tracking, and strategic decision-making.
This project aims to design and implement a comprehensive Enterprise Data Consolidation and Intelligence Framework that integrates all operational data into a unified, normalized, and analytics-ready architecture.
=== END REFERENCE STYLE ===

User Profile & Resume:
{resume_context}

Project Details:
{project_info}

Rules:
- Write exactly 120 to 180 words total. Do NOT exceed 180 words.
- Focus on the technical and business impact (e.g., performance efficiency, automation percentage gains, database structure optimization) in a factual manner.
- Do NOT use sensational language, clickbait, rhetorical questions, or emojis.
- Structure the post with:
  1. A clear, direct opening statement outlining the project goal and problem solved (no clickbait questions).
  2. 3 to 4 technical bullet points detailing the implementation, architecture, and accomplishments.
  3. A concise, professional closing statement inviting recruiters or technical managers to connect or discuss.
- Use plain, active English with executive tone.
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
                # 1. Query showcased projects from database
                stmt = select(ShowcasedProject.project_name)
                result = await db.execute(stmt)
                showcased_names = set(result.scalars().all())

                # 2. Filter unshowcased projects
                unshowcased = [p for p in projects if p.get("name") not in showcased_names]

                if not unshowcased:
                    # 3. All projects have been showcased! Reset history.
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

                # 4. Mark the selected project as showcased
                if selected:
                    new_showcase = ShowcasedProject(
                        project_name=selected.get("name"),
                        project_type=project_type
                    )
                    db.add(new_showcase)
                    await db.commit()

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
