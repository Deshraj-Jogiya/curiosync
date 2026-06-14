"""Draft model — stores generated LinkedIn post drafts."""

from datetime import datetime, date
from sqlalchemy import String, DateTime, Integer, ForeignKey, Text, Boolean, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.utils.timezone import now_phoenix


class Draft(Base):
    __tablename__ = "drafts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    word_count: Mapped[int] = mapped_column(Integer)
    char_count: Mapped[int] = mapped_column(Integer)
    tone: Mapped[str] = mapped_column(String(50), default="professional")
    sources_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    compliance_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    date_for: Mapped[date] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_phoenix)

    user = relationship("User", back_populates="drafts")
    post = relationship("PostHistory", back_populates="draft", uselist=False)
