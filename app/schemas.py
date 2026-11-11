"""Pydantic schemas for Linkly."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


class LinkCreate(BaseModel):
    """Payload for creating a short link."""

    long_url: HttpUrl
    custom_alias: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=30,
        description="Optional custom short code (letters, digits, - and _).",
    )
    expires_in_days: Optional[int] = Field(
        default=None, gt=0, le=3650, description="Optional lifetime in days."
    )

    @field_validator("custom_alias")
    @classmethod
    def alias_must_be_url_safe(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
        if not set(value) <= allowed:
            raise ValueError(
                "custom_alias may only contain letters, digits, '-' and '_'"
            )
        return value


class LinkOut(BaseModel):
    """A short link as returned by the API."""

    code: str
    long_url: str
    short_url: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    click_count: int = 0


class ReferrerStat(BaseModel):
    referrer: str
    clicks: int


class LinkStats(BaseModel):
    """Click analytics for one short link."""

    code: str
    long_url: str
    total_clicks: int
    clicks_per_day: dict[str, int]
    top_referrers: list[ReferrerStat]
