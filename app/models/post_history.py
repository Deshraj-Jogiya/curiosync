"""PostHistory model — records each LinkedIn publish attempt."""

from datetime import datetime, date
from sqlalchemy import String, DateTime, Integer, ForeignKey, Text, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.utils.timezone import now_phoenix


class PostHistory(Base):
    __tablename__ = "post_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    draft_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("drafts.id"), nullable=True)
    linkedin_post_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50))  # published, failed, duplicate
    content: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(DateTime, default=now_phoenix)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_for: Mapped[date] = mapped_column(Date, index=True)

    user = relationship("User", back_populates="posts")
    draft = relationship("Draft", back_populates="post")
