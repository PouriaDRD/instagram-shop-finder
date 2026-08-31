from pydantic import BaseModel, ConfigDict, Field

from app.models.external_link import ExternalLink


class RawProfileData(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    username: str = Field(
        min_length=1,
        max_length=30,
    )

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
