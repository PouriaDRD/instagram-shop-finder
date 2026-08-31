from enum import StrEnum

from pydantic import BaseModel, ConfigDict, HttpUrl


class ExternalLinkType(StrEnum):
    """Categorization enum for external link destinations associated with a profile."""

    WEBSITE = "website"
    LINK_IN_BIO = "link_in_bio"
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    SHOP = "shop"
    OTHER = "other"


class ExternalLink(BaseModel):
    """Schema representing an external link attached to a profile.

    Attributes:
        url: Validated HTTP/HTTPS target URL.
        title: Optional display label or title for the link.
        type: The link classification type (defaults to OTHER).
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    url: HttpUrl

    title: str | None = None

    type: ExternalLinkType = ExternalLinkType.OTHER
