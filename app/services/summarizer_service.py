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

FEATURABLE_TOPICS = [
    {
        "type": "experience",
        "company": "Objectways Technologies LLC",
        "role": "Teleoperation Data Collection Associate",
        "dates": "May 2026 - Present",
        "highlight": "collating and validating 10,000+ high-quality teleoperation data samples for AI/ML model training using Python-based workflows, improving dataset accuracy and consistency by 20%, and developing scalable data pipelines using Python, Scala, and Kubernetes to process large datasets, reducing processing time by 30%."
    },
    {
        "type": "experience",
        "company": "Technoid LLC",
        "role": "Applied Machine Learning Engineer",
        "dates": "Dec 2025 - May 2026",
        "highlight": "optimizing GPT-4o mini models for resume analysis/tailoring using OpenAI APIs, SQL, and PostgreSQL, improving recommendation accuracy by 25%, and establishing Supabase data sync with row-level security (RLS) fixes, reducing sync latency by 65% for real-time operations."
    },
    {
        "type": "experience",
        "company": "ElevateMe Bootcamp",
        "role": "Data Analytics & Machine Learning Fellow Trainee",
        "dates": "Jan 2025 - Mar 2026",
        "highlight": "conducting customer segmentation using K-Means clustering and PCA for dimensionality reduction, mapping results in Power BI to capture 92% of variance, and launching classification models that increased campaign click-through rates by 12%."
    },
    {
        "type": "experience",
        "company": "Zifatech Solutions LLC",
        "role": "Data Analyst",
        "dates": "Jun 2025 - Dec 2025",
        "highlight": "migrating legacy database workflows to AWS Glue and S3, increasing data availability by 60%, streamlining integration with Snowflake and Power BI, and transforming SQL/Python ETL pipelines to automate sales insights reporting (70% manual effort reduction) using Great Expectations QA validation."
    },
    {
        "type": "experience",
        "company": "Arizona State University",
        "role": "Data Engineer & Machine Learning Research Assistant",
        "dates": "Sep 2024 - Jun 2025",
        "highlight": "building a real-time streaming data pipeline utilizing Node.js and MongoDB (ensuring 99.9% uptime for 5,000 concurrent users), developing a personalized content recommendation engine that boosted click-through rates by 12%, and designing an NLP chatbot that analyzed user pain points."
    },
    {
        "type": "project",
        "name": "Multi-State Land Use Emissions Analysis",
        "dates": "Apr 2025 - Nov 2025",
        "highlight": "engineering a Python ETL pipeline for daily land cover datasets from 5 U.S. states, automating carbon emissions inventory compilation with geospatial data transformations, saving 10 hours weekly, and building Linear Regression/Random Forest models to forecast CO2 trends with 90% accuracy."
    },
    {
        "type": "project",
        "name": "AI-ML Data Science Simulation Project",
        "dates": "Apr 2024 - Jun 2024",
        "highlight": "creating a scalable data automation system using Python for daily sales data ingestion across 5 state branches, centralizing inventory data via SQL, and training Linear Regression/Random Forest models to achieve 90% forecast accuracy and cut stock-outs by 15%."
    },
    {
        "type": "project",
        "name": "Extending STEM across ASL",
        "dates": "Apr 2023 - Mar 2024",
        "highlight": "pioneering an inclusive Python platform using TensorFlow and Keras that enabled 7 STEM concepts for ASL-proficient students, creating a custom sign recognition algorithm that cut gesture redundancy and boosted learning efficiency by 30%."
    }
]

PERSONALIZED_POST_PROMPT = """\
You are a Senior Data & AI/ML Engineer. Write one highly engaging, human-written, and technically detailed LinkedIn post based on today's tech news.

Your writing style must match the following storytelling engineering structure:

=== REQUIRED STRUCTURE ===
1. TODAY'S TECH HIGHLIGHTS: Introduce the news with a clean, capitalized plain text header, accompanied by a relevant emoji (e.g., 🚀, 💻). Underneath, write a brief summary of the top worthy technical news formatted as 2-3 bulleted pointers (using •). Tastefully use emojis to make the bullet points visually appealing. Do NOT use markdown bold (e.g., **text**) or unicode bold alphanumeric characters (e.g., 𝗯𝗼𝗹𝗱) anywhere. Write all text as standard plain text only.

2. THE PERSONAL REFLECTION: Introduce a plain text section header with a relevant emoji (e.g., 🔍, ⚙️) highlighting a specific technical challenge (e.g., scale, data pipelines, model precision, data latency, etc.) related to the news.
You MUST tell a cohesive, focused story specifically about this engineering experience from your career:
{featured_accomplishment}

Maintain an authoritative, highly confident, and engineering tone throughout the post; avoid casual or blogger-style phrasing. Frame your credentials and experience with strong authority (e.g., referencing your graduate research at Arizona State University, 5 years of systems experience, or specific technical achievements). Clearly establish a direct connection: how the engineering challenges of today's tech news relate to what you built, what you achieved, and the engineering lessons learned. Do NOT use markdown bold asterisks or unicode bold characters anywhere. Use standard plain text only.

3. THE SYSTEM SIGNATURE & CALLS TO ACTION: Use plain text labels and clear formatting to present the pipeline signature and invites. It must be formatted exactly like this:

🤖 Automated Pipeline: This post was fully compiled and published by CurioSync (https://github.com/Deshraj-Jogiya/curiosync), my automated, self-hosted serverless data pipeline project.

🌐 Visit my live portfolio: deshraj-jogiya.github.io to play with the interactive SQL sandbox.

✉️ Hiring? Let's connect: State that you are currently seeking opportunities across the broader data engineering, machine learning, and analytics engineering landscape. Frame this as an eye-catching invitation for hiring managers and recruiters looking for a systems engineer ready to join.
=== END REQUIRED STRUCTURE ===

Your profile and context:
{resume_context}

Rules:
- Write in a natural, storytelling voice using short paragraphs separated by double line breaks for readability.
- Write exactly 220 to 320 words total. Do NOT exceed 320 words.
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
3. A transparent pipeline statement: "This post was fully compiled and published by CurioSync (https://github.com/Deshraj-Jogiya/curiosync), my automated, self-hosted serverless data pipeline project."
4. A Call to Action inviting readers to visit your live portfolio and interact with the SQL sandbox and chatbot assistant at deshraj-jogiya.github.io
5. A professional closing asking about available job opportunities and inviting recruiters/hiring managers to connect.
=== END REQUIRED STRUCTURE ===

=== REFERENCE POST TEMPLATE ===
Managing geospatial data in environmental analytics comes with unique challenges:
• Land cover datasets are fragmented across multiple states, causing severe processing bottlenecks.
• High latency in raster transformations delays downstream carbon emission forecasting.

To solve this, I engineered a Python ETL pipeline to automate the ingestion and geospatial transformation of massive datasets into a centralized SQL database. By integrating Linear Regression and Random Forest models, we began forecasting carbon trends based on land-use changes with a 90% forecasting accuracy, saving 10 engineering hours weekly. In production, this showed how critical robust pipelines are for turning raw spatial data into rapid, actionable insights.

This post was fully compiled and published by CurioSync (https://github.com/Deshraj-Jogiya/curiosync), my automated, self-hosted serverless data pipeline project. I invite you to visit my live portfolio at deshraj-jogiya.github.io to test my interactive SQL sandbox and query my career chatbot directly. I am currently seeking new opportunities as a Data Engineer or ML Engineer and would love to connect with engineering leaders and hiring teams. #DataEngineering #MachineLearning
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
    from datetime import datetime

    # Select featured topic using deterministic rotation based on the day of the year
    day_of_year = int(datetime.utcnow().strftime("%j"))
    topic_idx = day_of_year % len(FEATURABLE_TOPICS)
    topic = FEATURABLE_TOPICS[topic_idx]

    if topic["type"] == "experience":
        featured_accomplishment = (
            f"During my time working as a {topic['role']} at {topic['company']} from {topic['dates']}, "
            f"I was responsible for {topic['highlight']}"
        )
    else:
        featured_accomplishment = (
            f"In my project focusing on {topic['name']} from {topic['dates']}, "
            f"I was responsible for {topic['highlight']}"
        )

    logger.info("Selected featured topic for daily post: %s", featured_accomplishment)

    formatted = _format_news_for_prompt(news_items)
    resume_context = get_resume_context()
    prompt = PERSONALIZED_POST_PROMPT.format(
        resume_context=resume_context,
        news_items=formatted,
        featured_accomplishment=featured_accomplishment
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
