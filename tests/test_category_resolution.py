from datetime import (
    datetime,
    timezone,
)

from app.discovery.category_resolution import (
    CategoryEvidenceSource,
    CategoryResolver,
)
from app.models.candidate import (
    CandidateCategoryConfidence,
    CandidateDiscoveryEvidence,
    CandidateRetryContext,
    CandidateStatus,
    InstagramCandidate,
)
from app.models.profile import (
    InstagramProfile,
    ProfileCategory,
)

CURRENT_RUN = "current-run"
OLD_RUN = "old-run"
UNRELATED_RUN = "unrelated-run"


def make_profile(
    *,
    category: ProfileCategory,
    shop_score: float,
    is_shop: bool | None,
) -> InstagramProfile:
    return InstagramProfile(
        username="testshop",
        profile_url=("https://www.instagram.com/testshop/"),
        display_name="Test Shop",
        bio="Test profile",
        external_links=(),
        followers_count=50_000,
        following_count=100,
        posts_count=100,
        is_public=True,
        category=category,
        is_shop=is_shop,
        shop_score=shop_score,
        shop_signals=(),
    )


def make_candidate(
    *,
    evidence_run_id: str,
    evidence_category: ProfileCategory,
    retry_origin_run_id: str | None = None,
) -> InstagramCandidate:
    now = datetime.now(timezone.utc)

    retry_context = None

    if retry_origin_run_id is not None:
        retry_context = CandidateRetryContext(
            origin_run_id=(retry_origin_run_id),
            origin_status=(CandidateStatus.INCOMPLETE),
            started_at=now,
            retry_count=1,
        )

    return InstagramCandidate(
        username="testshop",
        profile_url=("https://www.instagram.com/testshop/"),
        status=(CandidateStatus.INCOMPLETE if retry_context else CandidateStatus.NEW),
        discovery_evidence=[
            CandidateDiscoveryEvidence(
                run_id=(evidence_run_id),
                category=(evidence_category),
                query=("site:instagram.com " '"فروشگاه اسباب بازی"'),
                source=("TestDiscoverySource"),
                discovered_at=now,
            )
        ],
        retry_context=(retry_context),
        first_discovered_at=now,
        last_discovered_at=now,
    )


def test_exact_classifier_category_is_confirmed() -> None:
    result = CategoryResolver().resolve(
        profile=make_profile(
            category=(ProfileCategory.TOYS),
            shop_score=0.60,
            is_shop=True,
        ),
        candidate=None,
        requested_category=(ProfileCategory.TOYS),
        minimum_shop_score=0.30,
        current_run_id=(CURRENT_RUN),
    )

    assert result.confidence == CandidateCategoryConfidence.CONFIRMED

    assert result.evidence_source == CategoryEvidenceSource.CLASSIFIER


def test_classifier_conflict_cannot_be_overridden() -> None:
    candidate = make_candidate(
        evidence_run_id=(CURRENT_RUN),
        evidence_category=(ProfileCategory.TOYS),
    )

    result = CategoryResolver().resolve(
        profile=make_profile(
            category=(ProfileCategory.CLOTHING),
            shop_score=1.0,
            is_shop=True,
        ),
        candidate=candidate,
        requested_category=(ProfileCategory.TOYS),
        minimum_shop_score=0.30,
        current_run_id=(CURRENT_RUN),
    )

    assert result.confidence == CandidateCategoryConfidence.CONFLICT


def test_current_run_evidence_supports_probable_category() -> None:
    candidate = make_candidate(
        evidence_run_id=(CURRENT_RUN),
        evidence_category=(ProfileCategory.TOYS),
    )

    result = CategoryResolver().resolve(
        profile=make_profile(
            category=(ProfileCategory.UNKNOWN),
            shop_score=0.80,
            is_shop=True,
        ),
        candidate=candidate,
        requested_category=(ProfileCategory.TOYS),
        minimum_shop_score=0.30,
        current_run_id=(CURRENT_RUN),
    )

    assert result.confidence == CandidateCategoryConfidence.PROBABLE

    assert result.effective_category == ProfileCategory.TOYS

    assert result.evidence_source == CategoryEvidenceSource.CURRENT_RUN


def test_retry_origin_evidence_is_valid() -> None:
    candidate = make_candidate(
        evidence_run_id=(OLD_RUN),
        evidence_category=(ProfileCategory.TOYS),
        retry_origin_run_id=(OLD_RUN),
    )

    result = CategoryResolver().resolve(
        profile=make_profile(
            category=(ProfileCategory.UNKNOWN),
            shop_score=0.80,
            is_shop=True,
        ),
        candidate=candidate,
        requested_category=(ProfileCategory.TOYS),
        minimum_shop_score=0.30,
        current_run_id=(CURRENT_RUN),
    )

    assert result.confidence == CandidateCategoryConfidence.PROBABLE

    assert result.effective_category == ProfileCategory.TOYS

    assert result.evidence_source == CategoryEvidenceSource.RETRY_ORIGIN


def test_old_evidence_without_retry_context_is_invalid() -> None:
    candidate = make_candidate(
        evidence_run_id=(OLD_RUN),
        evidence_category=(ProfileCategory.TOYS),
    )

    result = CategoryResolver().resolve(
        profile=make_profile(
            category=(ProfileCategory.UNKNOWN),
            shop_score=1.0,
            is_shop=True,
        ),
        candidate=candidate,
        requested_category=(ProfileCategory.TOYS),
        minimum_shop_score=0.30,
        current_run_id=(CURRENT_RUN),
    )

    assert result.confidence == CandidateCategoryConfidence.UNKNOWN

    assert result.evidence_source == CategoryEvidenceSource.NONE


def test_unrelated_history_not_valid_even_with_retry_context() -> None:
    now = datetime.now(timezone.utc)

    candidate = InstagramCandidate(
        username="testshop",
        profile_url=("https://www.instagram.com/testshop/"),
        status=(CandidateStatus.INCOMPLETE),
        discovery_evidence=[
            CandidateDiscoveryEvidence(
                run_id=(UNRELATED_RUN),
                category=(ProfileCategory.TOYS),
                query="old unrelated query",
                source="OldSource",
                discovered_at=now,
            ),
        ],
        retry_context=(
            CandidateRetryContext(
                origin_run_id=(OLD_RUN),
                origin_status=(CandidateStatus.INCOMPLETE),
                started_at=now,
                retry_count=1,
            )
        ),
        first_discovered_at=now,
        last_discovered_at=now,
    )

    result = CategoryResolver().resolve(
        profile=make_profile(
            category=(ProfileCategory.UNKNOWN),
            shop_score=1.0,
            is_shop=True,
        ),
        candidate=candidate,
        requested_category=(ProfileCategory.TOYS),
        minimum_shop_score=0.30,
        current_run_id=(CURRENT_RUN),
    )

    assert result.confidence == CandidateCategoryConfidence.UNKNOWN

    assert result.evidence_source == CategoryEvidenceSource.NONE


def test_retry_origin_still_requires_strong_shop_evidence() -> None:
    candidate = make_candidate(
        evidence_run_id=(OLD_RUN),
        evidence_category=(ProfileCategory.TOYS),
        retry_origin_run_id=(OLD_RUN),
    )

    result = CategoryResolver().resolve(
        profile=make_profile(
            category=(ProfileCategory.UNKNOWN),
            shop_score=0.30,
            is_shop=True,
        ),
        candidate=candidate,
        requested_category=(ProfileCategory.TOYS),
        minimum_shop_score=0.20,
        current_run_id=(CURRENT_RUN),
    )

    assert result.confidence == CandidateCategoryConfidence.UNKNOWN


def test_retry_origin_does_not_override_real_classifier_conflict() -> None:
    candidate = make_candidate(
        evidence_run_id=(OLD_RUN),
        evidence_category=(ProfileCategory.TOYS),
        retry_origin_run_id=(OLD_RUN),
    )

    result = CategoryResolver().resolve(
        profile=make_profile(
            category=(ProfileCategory.ACCESSORIES),
            shop_score=1.0,
            is_shop=True,
        ),
        candidate=candidate,
        requested_category=(ProfileCategory.TOYS),
        minimum_shop_score=0.20,
        current_run_id=(CURRENT_RUN),
    )

    assert result.confidence == CandidateCategoryConfidence.CONFLICT
