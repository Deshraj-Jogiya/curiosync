"""Model to track showcased projects for Monday spotlight posts."""

from datetime import datetime
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.utils.timezone import now_phoenix


class ShowcasedProject(Base):
    __tablename__ = "showcased_projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    project_type: Mapped[str] = mapped_column(String(50))  # "github" or "resume"
    showcased_at: Mapped[datetime] = mapped_column(DateTime, default=now_phoenix)
