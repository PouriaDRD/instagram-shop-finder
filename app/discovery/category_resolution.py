from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.models.candidate import (
    CandidateCategoryConfidence,
    InstagramCandidate,
)
from app.models.profile import (
    InstagramProfile,
    ProfileCategory,
)


class CategoryEvidenceSource(
    str,
    Enum,
):
    CLASSIFIER = "classifier"

    CURRENT_RUN = "current_run"

    RETRY_ORIGIN = "retry_origin"

    NONE = "none"


@dataclass(
    frozen=True,
    slots=True,
)
class CategoryResolution:
    effective_category: ProfileCategory

    confidence: CandidateCategoryConfidence

    reason: str

    evidence_source: CategoryEvidenceSource


class CategoryResolver:
    """Conservative category resolution.

    Evidence priority:

    1. Explicit classifier result
    2. Current-run discovery evidence
    3. Retry-origin evidence
    4. Nothing

    Historical unrelated evidence is never used.
    """

    DEFAULT_PROBABLE_SCORE_THRESHOLD = 0.60

    HIGH_SCORE_WITHOUT_SHOP_FLAG = 0.75

    def __init__(
        self,
        *,
        probable_score_threshold: float = (DEFAULT_PROBABLE_SCORE_THRESHOLD),
    ) -> None:
        if not (0.0 <= probable_score_threshold <= 1.0):
            raise ValueError("probable_score_threshold must " "be between 0 and 1.")

        self._probable_score_threshold = probable_score_threshold

    @staticmethod
    def _has_category_evidence(
        *,
        candidate: InstagramCandidate,
        run_id: str,
        requested_category: ProfileCategory,
    ) -> bool:
        return any(
            (evidence.run_id == run_id and evidence.category == requested_category)
            for evidence in candidate.discovery_evidence
        )

    def _resolve_discovery_evidence_source(
        self,
        *,
        candidate: InstagramCandidate,
        current_run_id: str,
        requested_category: ProfileCategory,
    ) -> CategoryEvidenceSource:
        if self._has_category_evidence(
            candidate=candidate,
            run_id=current_run_id,
            requested_category=(requested_category),
        ):
            return CategoryEvidenceSource.CURRENT_RUN

        retry_context = candidate.retry_context

        if retry_context is None:
            return CategoryEvidenceSource.NONE

        if self._has_category_evidence(
            candidate=candidate,
            run_id=(retry_context.origin_run_id),
            requested_category=(requested_category),
        ):
            return CategoryEvidenceSource.RETRY_ORIGIN

        return CategoryEvidenceSource.NONE

    def resolve(
        self,
        *,
        profile: InstagramProfile,
        candidate: InstagramCandidate | None,
        requested_category: ProfileCategory | None,
        minimum_shop_score: float,
        current_run_id: str,
    ) -> CategoryResolution:
        detected = profile.category

        if requested_category is None:
            if detected == ProfileCategory.UNKNOWN:
                return CategoryResolution(
                    effective_category=(ProfileCategory.UNKNOWN),
                    confidence=(CandidateCategoryConfidence.UNKNOWN),
                    reason=("no category requested and " "classifier returned unknown"),
                    evidence_source=(CategoryEvidenceSource.NONE),
                )

            return CategoryResolution(
                effective_category=detected,
                confidence=(CandidateCategoryConfidence.CONFIRMED),
                reason=("classifier category accepted"),
                evidence_source=(CategoryEvidenceSource.CLASSIFIER),
            )

        # Strongest possible evidence.
        if detected == requested_category:
            return CategoryResolution(
                effective_category=detected,
                confidence=(CandidateCategoryConfidence.CONFIRMED),
                reason=("classifier confirmed " f"{requested_category.value}"),
                evidence_source=(CategoryEvidenceSource.CLASSIFIER),
            )

        # Explicit conflict must never be overridden.
        if detected != ProfileCategory.UNKNOWN:
            return CategoryResolution(
                effective_category=detected,
                confidence=(CandidateCategoryConfidence.CONFLICT),
                reason=(
                    "classifier detected "
                    f"{detected.value} instead of "
                    f"{requested_category.value}"
                ),
                evidence_source=(CategoryEvidenceSource.CLASSIFIER),
            )

        if candidate is None:
            return CategoryResolution(
                effective_category=(ProfileCategory.UNKNOWN),
                confidence=(CandidateCategoryConfidence.UNKNOWN),
                reason=(
                    "classifier returned unknown "
                    "and candidate evidence is unavailable"
                ),
                evidence_source=(CategoryEvidenceSource.NONE),
            )

        evidence_source = self._resolve_discovery_evidence_source(
            candidate=candidate,
            current_run_id=(current_run_id),
            requested_category=(requested_category),
        )

        if evidence_source == CategoryEvidenceSource.NONE:
            return CategoryResolution(
                effective_category=(ProfileCategory.UNKNOWN),
                confidence=(CandidateCategoryConfidence.UNKNOWN),
                reason=(
                    "classifier returned unknown and "
                    "no valid current-run or retry-origin "
                    "category evidence exists"
                ),
                evidence_source=(CategoryEvidenceSource.NONE),
            )

        score = profile.shop_score if profile.shop_score is not None else 0.0

        required_score = max(
            minimum_shop_score,
            self._probable_score_threshold,
        )

        if score < required_score:
            return CategoryResolution(
                effective_category=(ProfileCategory.UNKNOWN),
                confidence=(CandidateCategoryConfidence.UNKNOWN),
                reason=(
                    f"{evidence_source.value} discovery "
                    f"suggests {requested_category.value}, "
                    "but shop evidence is not strong "
                    "enough for probable resolution"
                ),
                evidence_source=(evidence_source),
            )

        if profile.is_shop is not True and score < self.HIGH_SCORE_WITHOUT_SHOP_FLAG:
            return CategoryResolution(
                effective_category=(ProfileCategory.UNKNOWN),
                confidence=(CandidateCategoryConfidence.UNKNOWN),
                reason=(
                    f"{evidence_source.value} category "
                    "evidence exists but shop evidence "
                    "remains ambiguous"
                ),
                evidence_source=(evidence_source),
            )

        return CategoryResolution(
            effective_category=(requested_category),
            confidence=(CandidateCategoryConfidence.PROBABLE),
            reason=(
                "classifier returned unknown; "
                f"{evidence_source.value} discovery "
                f"evidence plus shop score "
                f"{score:.0%} supports probable "
                f"{requested_category.value}"
            ),
            evidence_source=(evidence_source),
        )
