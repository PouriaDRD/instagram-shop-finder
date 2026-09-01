from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ProfileDataQualityStatus(
    str,
    Enum,
):
    COMPLETE = "complete"

    INCOMPLETE = "incomplete"


class ProfileDataQuality(BaseModel):
    status: ProfileDataQualityStatus

    reasons: list[str] = Field(
        default_factory=list,
    )

    @property
    def is_complete(self) -> bool:
        return self.status == ProfileDataQualityStatus.COMPLETE
