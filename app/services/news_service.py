from datetime import date, datetime, timedelta

import feedparser
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.source import NewsSource
from app.services.deduplication_service import generate_dedup_hash
from app.utils.logging import logger
from app.utils.timezone import today_phoenix

RSS_FEEDS: dict[str, str] = {
    "TechCrunch": "https://techcrunch.com/feed/",
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index",
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "Wired": "https://www.wired.com/feed/rss",
    "Reuters Tech": "https://www.rssboard.org/rss-specification",
    "BBC Tech": "http://feeds.bbci.co.uk/news/technology/rss.xml",
}

SOURCE_CREDIBILITY: dict[str, float] = {
    "TechCrunch": 1.0,
    "Ars Technica": 1.0,
    "Wired": 1.0,
    "BBC Tech": 1.0,
    "The Verge": 0.8,
    "Reuters Tech": 0.8,
}


def _parse_published(entry: dict) -> datetime | None:
    """Extract a datetime from a feed entry's published or updated fields."""
    for field in ("published_parsed", "updated_parsed"):
        tp = entry.get(field)
        if tp:
            try:
                return datetime(*tp[:6])
            except Exception:
                continue
    return None


def _is_today(dt: datetime | None, reference: date) -> bool:
    if dt is None:
        return True  # keep items with unknown dates (err on the side of inclusion)
    return dt.date() == reference


async def fetch_news(settings: Settings) -> list[dict]:
    """Fetch and parse all RSS feeds, returning today's top 15 items sorted by credibility."""
    today = today_phoenix()
    all_items: list[dict] = []

    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        for source_name, feed_url in RSS_FEEDS.items():
            try:
                resp = await client.get(feed_url)
                resp.raise_for_status()
                feed = feedparser.parse(resp.text)

                for entry in feed.entries:
                    published = _parse_published(entry)
                    # Include articles from today and yesterday (to ensure a rich news pool on weekends/off-peak times)
                    if published is not None and published.date() < today - timedelta(days=1):
                        continue

                    summary = entry.get("summary", "") or ""
                    # Strip HTML tags from summary (basic)
                    if "<" in summary:
                        import re
                        summary = re.sub(r"<[^>]+>", "", summary)

                    item = {
                        "title": entry.get("title", "").strip(),
                        "url": entry.get("link", "").strip(),
                        "source_name": source_name,
                        "summary": summary.strip()[:500],
                        "published_at": published.isoformat() if published else None,
                        "relevance_score": SOURCE_CREDIBILITY.get(source_name, 0.8),
                    }
                    if item["title"] and item["url"]:
                        all_items.append(item)

                logger.info(
                    "Fetched RSS feed",
                    extra={"source": source_name, "entries": len(feed.entries)},
                )
            except Exception as exc:
                logger.warning(
                    "Failed to fetch RSS feed",
                    extra={"source": source_name, "error": str(exc)},
                )
                continue

    # Sort by credibility descending, then by published_at descending
    all_items.sort(key=lambda x: x["relevance_score"], reverse=True)
    top_items = all_items[:15]
    logger.info("News fetch complete", extra={"total": len(all_items), "returned": len(top_items)})
    return top_items


async def save_news_items(
    db: AsyncSession,
    items: list[dict],
    date_for: date,
) -> list[NewsSource]:
    """Persist fetched news items to the database."""
    saved: list[NewsSource] = []
    for item in items:
        published_at = None
        if item.get("published_at"):
            try:
                published_at = datetime.fromisoformat(item["published_at"])
            except (ValueError, TypeError):
                pass

        record = NewsSource(
            title=item["title"],
            url=item["url"],
            source_name=item["source_name"],
            summary=item.get("summary"),
            published_at=published_at,
            relevance_score=item.get("relevance_score", 0.0),
            dedup_hash=generate_dedup_hash(item["title"]),
            date_for=date_for,
        )
        db.add(record)
        saved.append(record)

    await db.flush()
    logger.info("Saved news items to DB", extra={"count": len(saved)})
    return saved
