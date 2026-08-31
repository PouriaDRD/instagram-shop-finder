from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ProfileCategory(StrEnum):
    BEAUTY = "beauty"
    FASHION = "fashion"
    CLOTHING = "clothing"
    HOME = "home"
    ACCESSORIES = "accessories"
    UNKNOWN = "unknown"


class InstagramProfile(BaseModel):
    model_config = ConfigDict(
        frozen=False,
        extra="forbid",
        validate_assignment=True,
    )

    username: str = Field(
        min_length=1,
        max_length=30,
    )

    display_name: str | None = None

    bio: str | None = None

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

    discovered_at: datetime = Field(
        default_factory=datetime.now,
    )
