"""OAuth token model with Fernet encryption for access tokens."""

from datetime import datetime
from sqlalchemy import String, DateTime, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from cryptography.fernet import Fernet
from app.database import Base
from app.utils.timezone import now_phoenix


class OAuthToken(Base):
    __tablename__ = "oauth_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    encrypted_access_token: Mapped[str] = mapped_column(Text)
    token_type: Mapped[str] = mapped_column(String(50), default="Bearer")
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    scopes: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_phoenix)

    user = relationship("User", back_populates="tokens")

    def decrypt_access_token(self, fernet_key: str) -> str:
        f = Fernet(fernet_key.encode() if isinstance(fernet_key, str) else fernet_key)
        return f.decrypt(self.encrypted_access_token.encode()).decode()

    @staticmethod
    def encrypt_token(token: str, fernet_key: str) -> str:
        f = Fernet(fernet_key.encode() if isinstance(fernet_key, str) else fernet_key)
        return f.encrypt(token.encode()).decode()

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() >= self.expires_at

    @property
    def expires_soon(self) -> bool:
        """Returns True if token expires within 7 days."""
        from datetime import timedelta
        return datetime.utcnow() >= (self.expires_at - timedelta(days=7))
