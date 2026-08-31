from enum import StrEnum

from pydantic import BaseModel, ConfigDict, HttpUrl


class ExternalLinkType(StrEnum):
    WEBSITE = "website"

    INSTAGRAM = "instagram"
    THREADS = "threads"
    TWITTER = "twitter"
    YOUTUBE = "youtube"
    LINKEDIN = "linkedin"
    FACEBOOK = "facebook"
    TIKTOK = "tiktok"
    PINTEREST = "pinterest"
    SNAPCHAT = "snapchat"

    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"

    LINK_IN_BIO = "link_in_bio"
    MAPS = "maps"
    SHOP = "shop"

    OTHER = "other"


class ExternalLink(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    url: HttpUrl
    title: str | None = None
    type: ExternalLinkType = ExternalLinkType.OTHER
