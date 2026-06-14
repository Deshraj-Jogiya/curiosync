"""User model — stores LinkedIn profile information."""

from datetime import datetime
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.utils.timezone import now_phoenix


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    linkedin_sub: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    profile_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    picture_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_phoenix)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_phoenix, onupdate=now_phoenix)

    tokens = relationship("OAuthToken", back_populates="user", cascade="all, delete-orphan")
    drafts = relationship("Draft", back_populates="user", cascade="all, delete-orphan")
    posts = relationship("PostHistory", back_populates="user", cascade="all, delete-orphan")
