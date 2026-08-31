from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.models.external_link import ExternalLink


class ProfileCategory(StrEnum):
    BEAUTY = "beauty"
    FASHION = "fashion"
    CLOTHING = "clothing"
    HOME = "home"
    ACCESSORIES = "accessories"
    UNKNOWN = "unknown"


class InstagramProfile(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    username: str = Field(
        min_length=1,
        max_length=30,
    )

    profile_url: str

    display_name: str | None = None

    bio: str | None = None

    external_links: tuple[ExternalLink, ...] = ()

    followers_count: int = Field(
        default=0,
        ge=0,
    )

    following_count: int = Field(
        default=0,
        ge=0,
    )

    posts_count: int = Field(
        default=0,
        ge=0,
    )

    is_public: bool = True

    category: ProfileCategory = ProfileCategory.UNKNOWN

    is_shop: bool | None = None

    shop_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    shop_signals: tuple[str, ...] = ()

    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_data(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        migrated_data = dict(data)

        username = migrated_data.get("username")

        if not migrated_data.get("profile_url") and isinstance(username, str):
            normalized_username = username.strip().lstrip("@").lower()

            if normalized_username:
                migrated_data["profile_url"] = (
                    "https://www.instagram.com/" f"{normalized_username}/"
                )

        legacy_external_url = migrated_data.pop(
            "external_url",
            None,
        )

        if legacy_external_url and not migrated_data.get("external_links"):
            migrated_data["external_links"] = [
                {
                    "url": legacy_external_url,
                    "title": None,
                    "type": "other",
                }
            ]

        return migrated_data
