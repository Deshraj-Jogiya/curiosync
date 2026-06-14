"""News-related schemas."""

from pydantic import BaseModel


class NewsItem(BaseModel):
    title: str
    url: str
    source_name: str
    summary: str | None = None
    published_at: str | None = None
    relevance_score: float = 0.0


class NewsFetchResponse(BaseModel):
    items: list[NewsItem]
    count: int
    fetched_at: str
