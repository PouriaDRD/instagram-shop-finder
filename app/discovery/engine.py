"""Automatic discovery pipeline for Instagram shops."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

from app.classifiers.category_classifier import (
    CategoryClassifier,
)
from app.classifiers.link_classifier import (
    LinkClassifier,
)
from app.classifiers.shop_classifier import (
    ShopClassifier,
)
from app.cli.reprocess_command import (
    apply_classifications,
)
from app.config import (
    CANDIDATES_FILE,
    LATEST_DISCOVERY_FILE,
    LATEST_VALIDATION_FILE,
)
from app.crawler.crawl_session import (
    InstagramCrawlSession,
)
from app.crawler.exceptions import (
    CrawlSessionStoppedError,
    ProfileFetchError,
)
from app.crawler.profile_quality import (
    ProfileQualityEvaluator,
)
from app.discovery.base import (
    DiscoverySource,
)
from app.discovery.category_resolution import (
    CategoryResolver,
)
from app.filters.profile_filter import (
    ProfileFilter,
    ProfileFilterEngine,
)
from app.models.candidate import (
    CandidateCategoryConfidence,
    CandidateStatus,
)
from app.models.profile import (
    InstagramProfile,
    ProfileCategory,
)
from app.models.raw_profile import (
    RawProfileData,
)
from app.storage.candidate_storage import (
    CandidateStorage,
)
from app.storage.profile_storage import (
    ProfileStorage,
)
from app.storage.run_snapshot_storage import (
    RunSnapshotStorage,
)


@dataclass(
    frozen=True,
    slots=True,
)
class DiscoveryCriteria:
    category: ProfileCategory | None

    target_results: int = 20

    min_followers: int | None = None

    max_followers: int | None = None

    min_shop_score: float = 0.60

    additional_query: str | None = None

    max_candidates: int = 500

    def __post_init__(
        self,
    ) -> None:
        if self.target_results <= 0:
            raise ValueError("target_results must be greater than zero.")

        if self.max_candidates <= 0:
            raise ValueError("max_candidates must be greater than zero.")

        if self.min_followers is not None and self.min_followers < 0:
            raise ValueError("min_followers cannot be negative.")

        if self.max_followers is not None and self.max_followers < 0:
            raise ValueError("max_followers cannot be negative.")

        if (
            self.min_followers is not None
            and self.max_followers is not None
            and self.min_followers > self.max_followers
        ):
            raise ValueError("min_followers cannot be greater " "than max_followers.")

        if not (0.0 <= self.min_shop_score <= 1.0):
            raise ValueError("min_shop_score must be between 0 and 1.")


@dataclass(
    frozen=True,
    slots=True,
)
class DiscoveryResult:
    discovered_candidates: int

    checked_profiles: int

    matched_profiles: tuple[
        InstagramProfile,
        ...,
    ]

    rejected_profiles: int

    incomplete_profiles: int

    non_iranian_profiles: int

    failed_profiles: int

    skipped_existing: int

    stopped_by_rate_limit: bool


class InstagramShopDiscoveryEngine:
    """Public-web discovery + Instagram qualification."""

    INVALID_EXACT_USERNAMES: frozenset[str] = frozenset(
        {
            "your_username",
            "yourusername",
            "username",
            "user_name",
            "example",
            "example_user",
            "example_username",
            "example_shop",
            "instagram",
            "instagram_username",
            "profile",
            "account",
            "your_account",
            "your_instagram",
        }
    )

    _CATEGORY_SEARCH_TERMS: dict[
        ProfileCategory,
        tuple[str, ...],
    ] = {
        ProfileCategory.BEAUTY: (
            '"فروشگاه آرایشی"',
            '"فروشگاه آرایشی بهداشتی"',
            '"لوازم آرایشی"',
            '"لوازم آرایشی" خرید',
            '"لوازم آرایشی" ارسال',
            '"لوازم آرایشی" سفارش',
            '"محصولات آرایشی" خرید',
            '"محصولات آرایشی" ارسال',
            '"مراقبت پوست" خرید',
            '"مراقبت پوست" فروش',
            '"مراقبت پوست" سفارش',
            '"میکاپ" فروشگاه',
            '"آرایشی" دایرکت',
            '"آرایشی" سایت',
        ),
        ProfileCategory.CLOTHING: (
            '"فروشگاه لباس"',
            '"فروشگاه پوشاک"',
            '"لباس" خرید',
            '"لباس" ارسال',
            '"لباس" سفارش',
            '"پوشاک" خرید',
            '"پوشاک" ارسال',
            '"مانتو" فروشگاه',
            '"لباس زنانه" فروشگاه',
            '"لباس مردانه" فروشگاه',
            '"لباس زیر" فروشگاه',
            '"لباس زیر" خرید',
            '"لباس خواب" فروشگاه',
        ),
        ProfileCategory.FASHION: (
            '"فشن" فروشگاه',
            '"استایل" فروشگاه',
            '"استایل" خرید',
            '"فشن" خرید',
            '"بوتیک" فروشگاه',
        ),
        ProfileCategory.HOME: (
            '"فروشگاه لوازم خانگی"',
            '"لوازم خانگی" خرید',
            '"لوازم خانگی" ارسال',
            '"لوازم خانگی" سفارش',
            '"لوازم خانه" فروشگاه',
            '"لوازم خانه" خرید',
            '"لوازم آشپزخانه" فروشگاه',
            '"لوازم آشپزخانه" خرید',
            '"دکوراسیون" فروشگاه',
            '"دکور" خرید',
        ),
        ProfileCategory.ACCESSORIES: (
            '"فروشگاه اکسسوری"',
            '"اکسسوری" خرید',
            '"اکسسوری" ارسال',
            '"بدلیجات" فروشگاه',
            '"بدلیجات" خرید',
            '"زیورآلات" فروشگاه',
            '"زیورآلات" خرید',
            '"گردنبند" فروشگاه',
            '"دستبند" فروشگاه',
        ),
        ProfileCategory.TOYS: (
            '"فروشگاه اسباب بازی"',
            '"اسباب بازی" خرید',
            '"اسباب بازی" ارسال',
            '"اسباب بازی" سفارش',
            '"اسباب بازی" دایرکت',
            '"عروسک" فروشگاه',
            '"عروسک" خرید',
            '"لگو" فروشگاه',
            '"لگو" خرید',
            '"بازی فکری" فروشگاه',
            '"بازی فکری" خرید',
        ),
    }

    _FOREIGN_DOMAIN_SUFFIXES: tuple[
        str,
        ...,
    ] = (
        ".pk",
        ".com.pk",
        ".in",
        ".com.tr",
        ".tr",
        ".ae",
        ".co.uk",
    )

    _IRAN_SIGNALS: tuple[
        str,
        ...,
    ] = (
        "ایران",
        "تهران",
        "مشهد",
        "اصفهان",
        "شیراز",
        "تبریز",
        "کرج",
        "قم",
        "اهواز",
        "رشت",
        "گرگان",
        "چابهار",
        "آبادان",
        "سراسر کشور",
        "سراسر ایران",
    )

    def __init__(
        self,
        *,
        source: DiscoverySource,
        storage: ProfileStorage,
        candidate_storage: CandidateStorage | None = None,
        crawl_session: InstagramCrawlSession | None = None,
        shop_classifier: ShopClassifier | None = None,
        category_classifier: CategoryClassifier | None = None,
        link_classifier: LinkClassifier | None = None,
        filter_engine: ProfileFilterEngine | None = None,
        profile_quality_evaluator: ProfileQualityEvaluator | None = None,
        category_resolver: CategoryResolver | None = None,
        run_snapshot_storage: RunSnapshotStorage | None = None,
        before_crawl_callback: (
            Callable[
                [],
                bool,
            ]
            | None
        ) = None,
        network_recovery_callback: (
            Callable[
                [],
                bool,
            ]
            | None
        ) = None,
    ) -> None:
        self._source = source

        self._storage = storage

        self._candidate_storage = candidate_storage or CandidateStorage(CANDIDATES_FILE)

        self._crawl_session = crawl_session or InstagramCrawlSession()

        self._shop_classifier = shop_classifier or ShopClassifier()

        self._category_classifier = category_classifier or CategoryClassifier()

        self._link_classifier = link_classifier or LinkClassifier()

        self._filter_engine = filter_engine or ProfileFilterEngine()

        self._profile_quality_evaluator = (
            profile_quality_evaluator or ProfileQualityEvaluator()
        )

        self._category_resolver = category_resolver or CategoryResolver()

        self._run_snapshot_storage = run_snapshot_storage or RunSnapshotStorage(
            discovery_file=(LATEST_DISCOVERY_FILE),
            validation_file=(LATEST_VALIDATION_FILE),
        )

        self._before_crawl_callback = before_crawl_callback

        self._network_recovery_callback = network_recovery_callback

    @classmethod
    def _is_valid_candidate_username(
        cls,
        username: str,
    ) -> bool:
        normalized = username.strip().lstrip("@").lower()

        if not normalized:
            return False

        if normalized in cls.INVALID_EXACT_USERNAMES:
            return False

        if normalized.startswith("your_") and (
            "username" in normalized
            or "instagram" in normalized
            or "account" in normalized
        ):
            return False

        if "example_username" in normalized:
            return False

        return True

    @staticmethod
    def _profile_url(
        username: str,
    ) -> str:
        return "https://www.instagram.com/" f"{username}/"

    def _finish_snapshot(
        self,
        *,
        completed: bool = True,
        stop_reason: str | None = None,
    ) -> None:
        self._run_snapshot_storage.finish_run(
            completed=completed,
            stop_reason=stop_reason,
        )

    def discover(
        self,
        criteria: DiscoveryCriteria,
    ) -> DiscoveryResult:
        run_id = uuid4().hex

        self._run_snapshot_storage.start_run(
            run_id=run_id,
            category=criteria.category,
            min_followers=(criteria.min_followers),
            max_followers=(criteria.max_followers),
            min_shop_score=(criteria.min_shop_score),
            target_results=(criteria.target_results),
            additional_query=(criteria.additional_query),
            max_candidates=(criteria.max_candidates),
        )

        queries = self._build_queries(criteria)

        stored_usernames = {
            profile.username.lower() for profile in self._storage.get_all()
        }

        filter_criteria = ProfileFilter(
            is_shop=None,
            category=criteria.category,
            min_followers=(criteria.min_followers),
            max_followers=(criteria.max_followers),
            min_shop_score=(criteria.min_shop_score),
        )

        matches: list[InstagramProfile] = []

        current_run_candidates: list[str] = []

        seen_candidates: set[str] = set()

        discovered_candidates = 0
        checked_profiles = 0
        rejected_profiles = 0
        incomplete_profiles = 0
        non_iranian_profiles = 0
        failed_profiles = 0
        skipped_existing = 0
        stopped_by_rate_limit = False

        requested_category = criteria.category

        source_name = self._source.__class__.__name__

        # ==================================================
        # PHASE 1 - PUBLIC WEB DISCOVERY
        # ==================================================

        print()
        print("CANDIDATE DISCOVERY")
        print("-------------------")
        print("Searching public web sources...")
        print()
        print("Candidate budget : " f"up to {criteria.max_candidates:,}")
        print("Target shops     : " f"{criteria.target_results:,}")
        print()

        for query in queries:
            if discovered_candidates >= criteria.max_candidates:
                break

            remaining_budget = criteria.max_candidates - discovered_candidates

            query_limit = min(
                50,
                remaining_budget,
            )

            if query_limit <= 0:
                break

            try:
                candidates = self._source.discover(
                    query=query,
                    limit=query_limit,
                )

            except Exception as exc:
                print("[SOURCE WARNING] " f"{exc}")
                continue

            for username in candidates:
                normalized_username = username.strip().lstrip("@").lower()

                if not (self._is_valid_candidate_username(normalized_username)):
                    print(
                        "[IGNORED] "
                        f"@{normalized_username} "
                        "(placeholder / invalid username)"
                    )
                    continue

                if normalized_username in seen_candidates:
                    continue

                if discovered_candidates >= criteria.max_candidates:
                    break

                seen_candidates.add(normalized_username)

                discovered_candidates += 1

                current_run_candidates.append(normalized_username)

                is_new = self._candidate_storage.upsert_discovered(
                    username=(normalized_username),
                    query=query,
                    requested_category=(requested_category),
                    source=source_name,
                    run_id=run_id,
                )

                self._run_snapshot_storage.record_discovery_candidate(
                    username=(normalized_username),
                    profile_url=(self._profile_url(normalized_username)),
                    query=query,
                    source=source_name,
                    requested_category=(requested_category),
                    is_new_candidate=(is_new),
                )

                label = "NEW" if is_new else "KNOWN"

                print(
                    f"[{label} " f"#{discovered_candidates}] " f"@{normalized_username}"
                )

        print()
        print("Candidate collection complete.")
        print()
        print("Found this run : " f"{discovered_candidates:,}")
        print("Stored overall : " f"{self._candidate_storage.count():,}")

        # ==================================================
        # BUILD QUEUE
        # ==================================================

        queued_usernames: list[str] = []

        queue_seen: set[str] = set()

        for username in current_run_candidates:
            if username in queue_seen:
                continue

            queue_seen.add(username)

            queued_usernames.append(username)

        previous_pending = self._candidate_storage.get_processable_usernames(
            requested_category=(requested_category),
        )

        for username in previous_pending:
            if username in queue_seen:
                continue

            queue_seen.add(username)

            queued_usernames.append(username)

        current_run_candidate_set = set(current_run_candidates)

        print()
        print("Waiting for Instagram check: " f"{len(queued_usernames):,}")

        if not queued_usernames:
            self._finish_snapshot()

            return DiscoveryResult(
                discovered_candidates=(discovered_candidates),
                checked_profiles=0,
                matched_profiles=(),
                rejected_profiles=0,
                incomplete_profiles=0,
                non_iranian_profiles=0,
                failed_profiles=0,
                skipped_existing=0,
                stopped_by_rate_limit=False,
            )

        # ==================================================
        # NETWORK / VPN GATE
        # ==================================================

        if self._before_crawl_callback is not None:
            should_continue = self._before_crawl_callback()

            if not should_continue:
                self._finish_snapshot(
                    completed=False,
                    stop_reason=("cancelled_before_instagram_check"),
                )

                return DiscoveryResult(
                    discovered_candidates=(discovered_candidates),
                    checked_profiles=0,
                    matched_profiles=(),
                    rejected_profiles=0,
                    incomplete_profiles=0,
                    non_iranian_profiles=0,
                    failed_profiles=0,
                    skipped_existing=0,
                    stopped_by_rate_limit=False,
                )

        # ==================================================
        # PHASE 2 - INSTAGRAM
        # ==================================================

        print()
        print("INSTAGRAM PROFILE CHECK")
        print("-----------------------")
        print(f"{len(queued_usernames):,} " "profiles are in the queue.")

        consecutive_fetch_failures = 0
        queue_index = 0

        try:
            with self._crawl_session:
                while queue_index < len(queued_usernames):
                    if len(matches) >= criteria.target_results:
                        print()
                        print("[DONE] Target number " "of shops reached.")
                        break

                    normalized_username = queued_usernames[queue_index]

                    origin = (
                        "current_discovery"
                        if (normalized_username in current_run_candidate_set)
                        else "retry_pending"
                    )

                    profile_url = self._profile_url(normalized_username)

                    print()
                    print(
                        f"[CHECK "
                        f"{queue_index + 1}/"
                        f"{len(queued_usernames)}] "
                        f"@{normalized_username}"
                    )

                    # ======================================
                    # ALREADY SAVED
                    # ======================================

                    if normalized_username in stored_usernames:
                        skipped_existing += 1

                        existing_profile = self._storage.get_by_username(
                            normalized_username
                        )

                        self._candidate_storage.update_status(
                            normalized_username,
                            status=(CandidateStatus.ALREADY_SAVED),
                            current_run_id=run_id,
                            followers_count=(
                                existing_profile.followers_count
                                if existing_profile
                                else None
                            ),
                            detected_category=(
                                existing_profile.category if existing_profile else None
                            ),
                            resolved_category=(
                                existing_profile.category if existing_profile else None
                            ),
                            category_confidence=(
                                CandidateCategoryConfidence.CONFIRMED
                                if existing_profile
                                else None
                            ),
                            is_shop=(
                                existing_profile.is_shop if existing_profile else None
                            ),
                            shop_score=(
                                existing_profile.shop_score
                                if existing_profile
                                else None
                            ),
                        )

                        self._run_snapshot_storage.record_validation(
                            username=(normalized_username),
                            profile_url=(profile_url),
                            origin=origin,
                            result=("already_saved"),
                            followers_count=(
                                existing_profile.followers_count
                                if existing_profile
                                else None
                            ),
                            detected_category=(
                                existing_profile.category if existing_profile else None
                            ),
                            resolved_category=(
                                existing_profile.category if existing_profile else None
                            ),
                            category_confidence=(
                                CandidateCategoryConfidence.CONFIRMED.value
                                if existing_profile
                                else None
                            ),
                            shop_score=(
                                existing_profile.shop_score
                                if existing_profile
                                else None
                            ),
                            is_shop=(
                                existing_profile.is_shop if existing_profile else None
                            ),
                            reason=("already saved"),
                        )

                        print("  Result    : SKIP")
                        print("  Reason    : already saved")

                        queue_index += 1
                        continue

                    # ======================================
                    # FETCH
                    # ======================================

                    try:
                        raw = self._crawl_session.fetch(normalized_username)

                    except CrawlSessionStoppedError as exc:
                        stopped_by_rate_limit = True

                        self._candidate_storage.update_status(
                            normalized_username,
                            status=(CandidateStatus.RATE_LIMITED),
                            current_run_id=run_id,
                            error=str(exc),
                        )

                        self._run_snapshot_storage.record_validation(
                            username=(normalized_username),
                            profile_url=(profile_url),
                            origin=origin,
                            result=("rate_limited"),
                            reason=str(exc),
                        )

                        print("  Result    : PAUSED")
                        print("  Reason    : " "rate-limit safety stop")

                        break

                    except ProfileFetchError as exc:
                        failed_profiles += 1

                        consecutive_fetch_failures += 1

                        self._candidate_storage.update_status(
                            normalized_username,
                            status=(CandidateStatus.FETCH_FAILED),
                            current_run_id=run_id,
                            error=str(exc),
                        )

                        self._run_snapshot_storage.record_validation(
                            username=(normalized_username),
                            profile_url=(profile_url),
                            origin=origin,
                            result=("fetch_failed"),
                            reason=str(exc),
                        )

                        print("  Result    : FETCH FAILED")
                        print(f"  Error     : {exc}")

                        if consecutive_fetch_failures >= 5:
                            if self._network_recovery_callback is not None:
                                should_resume = self._network_recovery_callback()

                                if should_resume:
                                    consecutive_fetch_failures = 0

                                    print()
                                    print("Retrying current profile...")

                                    continue

                            break

                        queue_index += 1
                        continue

                    consecutive_fetch_failures = 0

                    checked_profiles += 1

                    # ======================================
                    # RAW -> PROFILE + CLASSIFICATION
                    # ======================================

                    profile = self._profile_from_raw(raw)

                    profile = apply_classifications(
                        profile,
                        shop_classifier=(self._shop_classifier),
                        category_classifier=(self._category_classifier),
                        link_classifier=(self._link_classifier),
                    )

                    original_category = profile.category

                    # ======================================
                    # DATA QUALITY
                    # ======================================

                    quality = self._profile_quality_evaluator.evaluate(
                        raw=raw,
                        profile=profile,
                        expected_category=(criteria.category),
                        min_shop_score=(criteria.min_shop_score),
                    )

                    if not quality.is_complete:
                        incomplete_profiles += 1

                        reason = "; ".join(quality.reasons)

                        self._candidate_storage.update_status(
                            normalized_username,
                            status=(CandidateStatus.INCOMPLETE),
                            current_run_id=run_id,
                            followers_count=(profile.followers_count),
                            detected_category=(original_category),
                            resolved_category=(ProfileCategory.UNKNOWN),
                            category_confidence=(CandidateCategoryConfidence.UNKNOWN),
                            is_shop=(profile.is_shop),
                            shop_score=(profile.shop_score),
                            incomplete_reason=(reason),
                        )

                        self._run_snapshot_storage.record_validation(
                            username=(normalized_username),
                            profile_url=(profile.profile_url),
                            origin=origin,
                            result=("incomplete"),
                            followers_count=(profile.followers_count),
                            detected_category=(original_category),
                            resolved_category=(ProfileCategory.UNKNOWN),
                            category_confidence=(
                                CandidateCategoryConfidence.UNKNOWN.value
                            ),
                            shop_score=(profile.shop_score),
                            is_shop=(profile.is_shop),
                            reason=reason,
                        )

                        print("  Result    : INCOMPLETE")
                        print("  Action    : saved for retry")
                        print(f"  Reason    : {reason}")

                        queue_index += 1
                        continue

                    # ======================================
                    # NON-IRANIAN
                    # ======================================

                    if self._is_clearly_non_iranian(
                        raw=raw,
                    ):
                        non_iranian_profiles += 1

                        self._candidate_storage.update_status(
                            normalized_username,
                            status=(CandidateStatus.REJECTED),
                            current_run_id=run_id,
                            followers_count=(profile.followers_count),
                            detected_category=(original_category),
                            resolved_category=(original_category),
                            category_confidence=(
                                CandidateCategoryConfidence.CONFIRMED
                                if (original_category != ProfileCategory.UNKNOWN)
                                else CandidateCategoryConfidence.UNKNOWN
                            ),
                            is_shop=(profile.is_shop),
                            shop_score=(profile.shop_score),
                            rejection_reason=("profile appears clearly non-Iranian"),
                        )

                        self._run_snapshot_storage.record_validation(
                            username=(normalized_username),
                            profile_url=(profile.profile_url),
                            origin=origin,
                            result=("non_iranian"),
                            followers_count=(profile.followers_count),
                            detected_category=(original_category),
                            resolved_category=(original_category),
                            shop_score=(profile.shop_score),
                            is_shop=(profile.is_shop),
                            reason=("profile appears clearly non-Iranian"),
                        )

                        print("  Result    : REJECT")
                        print("  Reason    : " "clearly non-Iranian profile")

                        queue_index += 1
                        continue

                    candidate = self._candidate_storage.get_by_username(
                        normalized_username
                    )

                    # ======================================
                    # CATEGORY RESOLUTION
                    # ======================================

                    resolution = self._category_resolver.resolve(
                        profile=profile,
                        candidate=candidate,
                        requested_category=(criteria.category),
                        minimum_shop_score=(criteria.min_shop_score),
                        current_run_id=(run_id),
                    )

                    # ======================================
                    # CATEGORY CONFLICT
                    # ======================================

                    if resolution.confidence == CandidateCategoryConfidence.CONFLICT:
                        rejected_profiles += 1

                        self._candidate_storage.update_status(
                            normalized_username,
                            status=(CandidateStatus.REJECTED),
                            current_run_id=run_id,
                            followers_count=(profile.followers_count),
                            detected_category=(original_category),
                            resolved_category=(resolution.effective_category),
                            category_confidence=(resolution.confidence),
                            is_shop=(profile.is_shop),
                            shop_score=(profile.shop_score),
                            rejection_reason=(resolution.reason),
                        )

                        self._run_snapshot_storage.record_validation(
                            username=(normalized_username),
                            profile_url=(profile.profile_url),
                            origin=origin,
                            result="rejected",
                            followers_count=(profile.followers_count),
                            detected_category=(original_category),
                            resolved_category=(resolution.effective_category),
                            category_confidence=(resolution.confidence.value),
                            evidence_source=(resolution.evidence_source.value),
                            shop_score=(profile.shop_score),
                            is_shop=(profile.is_shop),
                            reason=(resolution.reason),
                        )

                        print("  Followers : " f"{profile.followers_count:,}")
                        print("  Category  : " f"{original_category.value}")
                        print("  Result    : REJECT")
                        print("  Reason    : " f"{resolution.reason}")

                        queue_index += 1
                        continue

                    # ======================================
                    # CATEGORY UNRESOLVED
                    # ======================================

                    if (
                        criteria.category is not None
                        and resolution.confidence == CandidateCategoryConfidence.UNKNOWN
                    ):
                        rejected_profiles += 1

                        self._candidate_storage.update_status(
                            normalized_username,
                            status=(CandidateStatus.REJECTED),
                            current_run_id=run_id,
                            followers_count=(profile.followers_count),
                            detected_category=(original_category),
                            resolved_category=(ProfileCategory.UNKNOWN),
                            category_confidence=(resolution.confidence),
                            is_shop=(profile.is_shop),
                            shop_score=(profile.shop_score),
                            rejection_reason=(resolution.reason),
                        )

                        self._run_snapshot_storage.record_validation(
                            username=(normalized_username),
                            profile_url=(profile.profile_url),
                            origin=origin,
                            result="rejected",
                            followers_count=(profile.followers_count),
                            detected_category=(original_category),
                            resolved_category=(ProfileCategory.UNKNOWN),
                            category_confidence=(resolution.confidence.value),
                            evidence_source=(resolution.evidence_source.value),
                            shop_score=(profile.shop_score),
                            is_shop=(profile.is_shop),
                            reason=(resolution.reason),
                        )

                        print("  Followers : " f"{profile.followers_count:,}")
                        print("  Category  : unresolved")
                        print("  Shop score: " f"{self._score_label(profile)}")
                        print("  Result    : REJECT")
                        print("  Reason    : " f"{resolution.reason}")

                        queue_index += 1
                        continue

                    # ======================================
                    # APPLY RESOLVED CATEGORY
                    # ======================================

                    if resolution.effective_category != profile.category:
                        profile = profile.model_copy(
                            update={"category": (resolution.effective_category)}
                        )

                    category_label = profile.category.value

                    if resolution.confidence == CandidateCategoryConfidence.PROBABLE:
                        category_label += " (probable)"

                    print("  Followers : " f"{profile.followers_count:,}")
                    print("  Category  : " f"{category_label}")
                    print("  Shop score: " f"{self._score_label(profile)}")
                    print("  Shop flag : " f"{profile.is_shop}")

                    # ======================================
                    # FINAL FILTER
                    # ======================================

                    if not (
                        self._filter_engine.matches(
                            profile=profile,
                            criteria=(filter_criteria),
                        )
                    ):
                        rejected_profiles += 1

                        rejection_reason = self._build_rejection_reason(
                            profile=profile,
                            criteria=criteria,
                        )

                        self._candidate_storage.update_status(
                            normalized_username,
                            status=(CandidateStatus.REJECTED),
                            current_run_id=run_id,
                            followers_count=(profile.followers_count),
                            detected_category=(original_category),
                            resolved_category=(profile.category),
                            category_confidence=(resolution.confidence),
                            is_shop=(profile.is_shop),
                            shop_score=(profile.shop_score),
                            rejection_reason=(rejection_reason),
                        )

                        self._run_snapshot_storage.record_validation(
                            username=(normalized_username),
                            profile_url=(profile.profile_url),
                            origin=origin,
                            result="rejected",
                            followers_count=(profile.followers_count),
                            detected_category=(original_category),
                            resolved_category=(profile.category),
                            category_confidence=(resolution.confidence.value),
                            evidence_source=(resolution.evidence_source.value),
                            shop_score=(profile.shop_score),
                            is_shop=(profile.is_shop),
                            reason=(rejection_reason),
                        )

                        print("  Result    : REJECT")
                        print("  Reason    : " f"{rejection_reason}")

                        queue_index += 1
                        continue

                    # ======================================
                    # MATCH
                    # ======================================

                    self._storage.save(profile)

                    stored_usernames.add(profile.username.lower())

                    matches.append(profile)

                    self._candidate_storage.update_status(
                        normalized_username,
                        status=(CandidateStatus.MATCHED),
                        current_run_id=run_id,
                        followers_count=(profile.followers_count),
                        detected_category=(original_category),
                        resolved_category=(profile.category),
                        category_confidence=(resolution.confidence),
                        is_shop=(profile.is_shop),
                        shop_score=(profile.shop_score),
                    )

                    self._run_snapshot_storage.record_validation(
                        username=(normalized_username),
                        profile_url=(profile.profile_url),
                        origin=origin,
                        result="matched",
                        followers_count=(profile.followers_count),
                        detected_category=(original_category),
                        resolved_category=(profile.category),
                        category_confidence=(resolution.confidence.value),
                        evidence_source=(resolution.evidence_source.value),
                        shop_score=(profile.shop_score),
                        is_shop=(profile.is_shop),
                        reason=None,
                    )

                    print("  Result    : MATCH")

                    if resolution.confidence == CandidateCategoryConfidence.PROBABLE:
                        print(
                            "  Evidence  : "
                            f"{resolution.evidence_source.value} "
                            "+ shop signals"
                        )

                    print(
                        "  Progress  : "
                        f"{len(matches)}/"
                        f"{criteria.target_results} "
                        "target shops"
                    )

                    queue_index += 1

        except CrawlSessionStoppedError:
            stopped_by_rate_limit = True

        if stopped_by_rate_limit:
            self._finish_snapshot(
                completed=False,
                stop_reason=("rate_limit_safety_stop"),
            )
        else:
            self._finish_snapshot(
                completed=True,
            )

        return DiscoveryResult(
            discovered_candidates=(discovered_candidates),
            checked_profiles=(checked_profiles),
            matched_profiles=tuple(matches),
            rejected_profiles=(rejected_profiles),
            incomplete_profiles=(incomplete_profiles),
            non_iranian_profiles=(non_iranian_profiles),
            failed_profiles=(failed_profiles),
            skipped_existing=(skipped_existing),
            stopped_by_rate_limit=(stopped_by_rate_limit),
        )

    @staticmethod
    def _profile_from_raw(
        raw: RawProfileData,
    ) -> InstagramProfile:
        return InstagramProfile(
            username=raw.username,
            profile_url=("https://www.instagram.com/" f"{raw.username}/"),
            display_name=(raw.display_name),
            bio=raw.bio,
            external_links=(raw.external_links),
            followers_count=(raw.followers_count),
            following_count=(raw.following_count),
            posts_count=(raw.posts_count),
            is_public=(raw.is_public),
        )

    @staticmethod
    def _score_label(
        profile: InstagramProfile,
    ) -> str:
        if profile.shop_score is None:
            return "-"

        return f"{profile.shop_score:.0%}"

    @classmethod
    def _is_clearly_non_iranian(
        cls,
        *,
        raw: RawProfileData,
    ) -> bool:
        text = (f"{raw.display_name or ''} " f"{raw.bio or ''}").casefold()

        contains_persian = any("\u0600" <= char <= "\u06ff" for char in text)

        if contains_persian:
            return False

        if any(signal in text for signal in cls._IRAN_SIGNALS):
            return False

        for link in raw.external_links:
            url = str(link.url or "").casefold()

            if ".ir/" in url or url.endswith(".ir"):
                return False

            if any(suffix in url for suffix in cls._FOREIGN_DOMAIN_SUFFIXES):
                return True

        username = raw.username.casefold()

        if any(
            username.endswith(suffix)
            for suffix in (
                ".pk",
                ".tr",
                ".ae",
            )
        ):
            return True

        return False

    @staticmethod
    def _build_rejection_reason(
        *,
        profile: InstagramProfile,
        criteria: DiscoveryCriteria,
    ) -> str:
        reasons: list[str] = []

        if criteria.category is not None and profile.category != criteria.category:
            reasons.append("wrong category " f"({profile.category.value})")

        if (
            criteria.min_followers is not None
            and profile.followers_count < criteria.min_followers
        ):
            reasons.append(
                "followers below minimum "
                f"({profile.followers_count:,} "
                f"< "
                f"{criteria.min_followers:,})"
            )

        if (
            criteria.max_followers is not None
            and profile.followers_count > criteria.max_followers
        ):
            reasons.append(
                "followers above maximum "
                f"({profile.followers_count:,} "
                f"> "
                f"{criteria.max_followers:,})"
            )

        score = profile.shop_score if profile.shop_score is not None else 0.0

        if score < criteria.min_shop_score:
            reasons.append(
                "shop score too low "
                f"({score:.0%} "
                f"< "
                f"{criteria.min_shop_score:.0%})"
            )

        if not reasons:
            return "did not satisfy active filters"

        return "; ".join(reasons)

    def _build_queries(
        self,
        criteria: DiscoveryCriteria,
    ) -> tuple[str, ...]:
        additional = (
            criteria.additional_query.strip() if criteria.additional_query else ""
        )

        if criteria.category is None:
            categories = tuple(
                category
                for category in ProfileCategory
                if (category != ProfileCategory.UNKNOWN)
            )
        else:
            categories = (criteria.category,)

        queries: list[str] = []

        seen: set[str] = set()

        for category in categories:
            terms = self._CATEGORY_SEARCH_TERMS.get(
                category,
                (f'"{category.value}" ' '"فروشگاه"',),
            )

            for term in terms:
                parts = [
                    "site:instagram.com",
                    term,
                ]

                if additional:
                    parts.append(additional)

                query = " ".join(parts)

                normalized_query = query.casefold()

                if normalized_query in seen:
                    continue

                seen.add(normalized_query)

                queries.append(query)

        return tuple(queries)
