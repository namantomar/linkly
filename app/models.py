"""SQLAlchemy models for Linkly."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Link(Base):
    """A shortened link."""

    __tablename__ = "links"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(64), unique=True, index=True, nullable=False)
    long_url = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    clicks = relationship(
        "Click", back_populates="link", cascade="all, delete-orphan"
    )

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        # SQLite does not preserve tzinfo, so a stored timestamp comes back
        # naive; treat naive values as UTC.
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return expires <= _utcnow()


class Click(Base):
    """One recorded click on a shortened link."""

    __tablename__ = "clicks"

    id = Column(Integer, primary_key=True, index=True)
    link_id = Column(Integer, ForeignKey("links.id"), nullable=False, index=True)
    clicked_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    referrer = Column(String(2048), nullable=True)
    user_agent = Column(String(1024), nullable=True)

    link = relationship("Link", back_populates="clicks")
