"""Shared test fixtures and mock data."""

import asyncio
from datetime import datetime, date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base

# Sample mock news data — 15 realistic tech news items
MOCK_NEWS_ITEMS = [
    {
        "title": "OpenAI announces GPT-5 with improved reasoning capabilities",
        "url": "https://techcrunch.com/2026/01/15/openai-gpt5",
        "source_name": "TechCrunch",
        "summary": "OpenAI has unveiled GPT-5, featuring significantly improved logical reasoning and reduced hallucinations.",
        "published_at": datetime.now().isoformat(),
        "relevance_score": 1.0,
    },
    {
        "title": "Apple unveils M5 chip with 40% performance gains",
        "url": "https://arstechnica.com/apple/2026/01/m5-chip",
        "source_name": "Ars Technica",
        "summary": "Apple's new M5 chip delivers a 40% boost in CPU performance and 50% in GPU workloads.",
        "published_at": datetime.now().isoformat(),
        "relevance_score": 1.0,
    },
    {
        "title": "Microsoft acquires cybersecurity startup for $2 billion",
        "url": "https://www.theverge.com/2026/01/15/microsoft-acquisition",
        "source_name": "The Verge",
        "summary": "Microsoft is expanding its security portfolio with a major acquisition.",
        "published_at": datetime.now().isoformat(),
        "relevance_score": 0.8,
    },
    {
        "title": "Google Cloud launches new Kubernetes autoscaling features",
        "url": "https://www.wired.com/story/google-cloud-kubernetes",
        "source_name": "Wired",
        "summary": "New autoscaling capabilities aim to reduce cloud costs by up to 30%.",
        "published_at": datetime.now().isoformat(),
        "relevance_score": 1.0,
    },
    {
        "title": "TSMC begins 2nm chip production ahead of schedule",
        "url": "https://www.bbc.com/news/technology-tsmc-2nm",
        "source_name": "BBC Tech",
        "summary": "TSMC has started trial production of 2nm chips earlier than expected.",
        "published_at": datetime.now().isoformat(),
        "relevance_score": 1.0,
    },
    {
        "title": "GitHub Copilot adds multi-file editing support",
        "url": "https://techcrunch.com/2026/01/15/github-copilot-update",
        "source_name": "TechCrunch",
        "summary": "The AI coding assistant now supports editing across multiple files simultaneously.",
        "published_at": datetime.now().isoformat(),
        "relevance_score": 1.0,
    },
    {
        "title": "AWS reports record quarterly revenue driven by AI services",
        "url": "https://arstechnica.com/aws-revenue-2026",
        "source_name": "Ars Technica",
        "summary": "Amazon Web Services posted record revenue, with AI workloads driving much of the growth.",
        "published_at": datetime.now().isoformat(),
        "relevance_score": 1.0,
    },
    {
        "title": "EU passes comprehensive AI regulation framework",
        "url": "https://www.theverge.com/2026/eu-ai-regulation",
        "source_name": "The Verge",
        "summary": "The European Union has finalized its AI Act with strict requirements for high-risk systems.",
        "published_at": datetime.now().isoformat(),
        "relevance_score": 0.8,
    },
    {
        "title": "Tesla releases full self-driving software update v13",
        "url": "https://www.wired.com/story/tesla-fsd-v13",
        "source_name": "Wired",
        "summary": "Tesla's latest FSD update includes improved urban navigation and highway merging.",
        "published_at": datetime.now().isoformat(),
        "relevance_score": 1.0,
    },
    {
        "title": "Rust programming language reaches 2.0 milestone",
        "url": "https://www.bbc.com/news/technology-rust-2",
        "source_name": "BBC Tech",
        "summary": "The Rust programming language has officially released version 2.0 with async improvements.",
        "published_at": datetime.now().isoformat(),
        "relevance_score": 1.0,
    },
    {
        "title": "Samsung unveils 200MP mobile camera sensor",
        "url": "https://techcrunch.com/2026/01/15/samsung-200mp-sensor",
        "source_name": "TechCrunch",
        "summary": "Samsung's new ISOCELL sensor promises DSLR-quality photos on smartphones.",
        "published_at": datetime.now().isoformat(),
        "relevance_score": 1.0,
    },
    {
        "title": "Cloudflare launches AI-powered DDoS protection",
        "url": "https://arstechnica.com/cloudflare-ai-ddos",
        "source_name": "Ars Technica",
        "summary": "New AI system can detect and mitigate DDoS attacks in under 3 seconds.",
        "published_at": datetime.now().isoformat(),
        "relevance_score": 1.0,
    },
    {
        "title": "Docker Desktop adds native GPU support for AI workloads",
        "url": "https://www.theverge.com/2026/docker-gpu",
        "source_name": "The Verge",
        "summary": "Developers can now run GPU-accelerated containers directly in Docker Desktop.",
        "published_at": datetime.now().isoformat(),
        "relevance_score": 0.8,
    },
    {
        "title": "Intel announces new data center processors targeting AI inference",
        "url": "https://www.wired.com/story/intel-ai-inference",
        "source_name": "Wired",
        "summary": "Intel's new Xeon processors are optimized for running AI models at scale.",
        "published_at": datetime.now().isoformat(),
        "relevance_score": 1.0,
    },
    {
        "title": "Stack Overflow introduces AI-verified answers program",
        "url": "https://www.bbc.com/news/technology-stackoverflow-ai",
        "source_name": "BBC Tech",
        "summary": "Stack Overflow will use AI to flag and verify the accuracy of community answers.",
        "published_at": datetime.now().isoformat(),
        "relevance_score": 1.0,
    },
]

# Sample generated LinkedIn post from mock data
SAMPLE_LINKEDIN_POST = """Today's tech landscape is shaped by AI breakthroughs, next-gen silicon, and evolving regulation.

• OpenAI launched GPT-5 with stronger reasoning and fewer hallucinations — a meaningful step for enterprise adoption.
• Apple's M5 chip delivers 40% faster performance, while TSMC has begun 2nm production ahead of schedule.
• The EU finalized its AI Act, setting clear rules for high-risk systems across the bloc.
• GitHub Copilot now edits across multiple files, and AWS posted record revenue driven by AI workloads.
• Cloudflare introduced AI-powered DDoS protection that responds in under 3 seconds.

A day that underscores how infrastructure, policy, and tooling are all evolving to keep pace with AI's rapid expansion.

#TechNews #AI #Semiconductors #CloudComputing"""


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def mock_news_items():
    """Return the standard mock news dataset."""
    return MOCK_NEWS_ITEMS.copy()


@pytest.fixture
def sample_post():
    """Return a sample LinkedIn post."""
    return SAMPLE_LINKEDIN_POST
