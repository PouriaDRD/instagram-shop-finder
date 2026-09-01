from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.models.profile import ProfileCategory


class CandidateStatus(str, Enum):
    NEW = "new"
    FETCH_FAILED = "fetch_failed"
    RATE_LIMITED = "rate_limited"
    INCOMPLETE = "incomplete"
    REJECTED = "rejected"
    MATCHED = "matched"
    ALREADY_SAVED = "already_saved"


class CandidateCategoryConfidence(str, Enum):
    CONFIRMED = "confirmed"
    PROBABLE = "probable"
    UNKNOWN = "unknown"
    CONFLICT = "conflict"


class CandidateDiscoveryEvidence(BaseModel):
    """One concrete discovery observation."""

    run_id: str

    category: ProfileCategory | None = None

    query: str

    source: str

    discovered_at: datetime


class CandidateRetryContext(BaseModel):
    """Tracks the discovery origin of a retry chain.

    Example:

    Run A
      candidate discovered as toys
      crawl incomplete

    Run B
      candidate enters queue from pending storage
      but is not rediscovered

    The valid category evidence is still the discovery evidence
    from Run A, because this is a continuation of that exact
    candidate's failed/incomplete processing chain.
    """

    origin_run_id: str

    origin_status: CandidateStatus

    started_at: datetime

    retry_count: int = 0


class InstagramCandidate(BaseModel):
    """Persisted Instagram candidate / lead."""

    username: str

    profile_url: str

    status: CandidateStatus = CandidateStatus.NEW

    # Historical inspection fields.
    #
    # These fields MUST NOT be used directly by CategoryResolver.
    queries: list[str] = Field(
        default_factory=list,
    )

    sources: list[str] = Field(
        default_factory=list,
    )

    requested_categories: list[ProfileCategory] = Field(
        default_factory=list,
    )

    # Authoritative discovery observations.
    discovery_evidence: list[CandidateDiscoveryEvidence] = Field(
        default_factory=list,
    )

    # Present only while the candidate belongs to a retry chain.
    retry_context: CandidateRetryContext | None = None

    first_discovered_at: datetime

    last_discovered_at: datetime

    last_checked_at: datetime | None = None

    followers_count: int | None = None

    detected_category: ProfileCategory | None = None

    resolved_category: ProfileCategory | None = None

    category_confidence: CandidateCategoryConfidence | None = None

    is_shop: bool | None = None

    shop_score: float | None = None

    rejection_reason: str | None = None

    last_error: str | None = None

    incomplete_reason: str | None = None

    check_attempts: int = 0

    incomplete_attempts: int = 0
