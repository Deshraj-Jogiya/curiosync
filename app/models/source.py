"""NewsSource model — stores fetched tech news items."""

from datetime import datetime, date
from sqlalchemy import String, DateTime, Integer, Text, Float, Date
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.utils.timezone import now_phoenix


class NewsSource(Base):
    __tablename__ = "news_sources"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(512))
    url: Mapped[str] = mapped_column(String(1024))
    source_name: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=now_phoenix)
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    dedup_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    date_for: Mapped[date] = mapped_column(Date, index=True)
