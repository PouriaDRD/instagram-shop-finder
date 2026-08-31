"""Progressive automatic discovery pipeline for identifying and storing Instagram shop profiles."""

from dataclasses import dataclass

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
from app.crawler.crawl_session import (
    InstagramCrawlSession,
)
from app.crawler.exceptions import (
    CrawlSessionStoppedError,
    ProfileFetchError,
)
from app.discovery.base import (
    DiscoverySource,
)
from app.filters.profile_filter import (
    ProfileFilter,
    ProfileFilterEngine,
)
from app.models.profile import (
    InstagramProfile,
    ProfileCategory,
)
from app.models.raw_profile import (
    RawProfileData,
)
from app.storage.json_storage import (
    JsonProfileStorage,
)


@dataclass(
    frozen=True,
    slots=True,
)
class DiscoveryCriteria:
    """Configurable constraints and parameters governing a progressive discovery run.

    Attributes:
        category: Target ProfileCategory to search for (None searches across all categories).
        target_results: Maximum number of matching shop profiles to discover and save.
        min_followers: Optional minimum follower count threshold.
        max_followers: Optional maximum follower count threshold.
        min_shop_score: Minimum shop confidence score required to match (0.0 to 1.0).
        additional_query: Optional search keyword or phrase appended to search queries.
        max_candidates: Upper limit of total candidate handles to discover across queries.
    """

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
        """Validates logical bounds and relationships between discovery criteria fields."""
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
            raise ValueError("min_followers cannot be greater than max_followers.")

        if not (0.0 <= self.min_shop_score <= 1.0):
            raise ValueError("min_shop_score must be between 0 and 1.")


@dataclass(
    frozen=True,
    slots=True,
)
class DiscoveryResult:
    """Telemetry and profile collection outputs returned by a progressive discovery run.

    Attributes:
        discovered_candidates: Total count of unique candidate handles discovered across queries.
        checked_profiles: Total count of public Instagram profiles fetched successfully.
        matched_profiles: Tuple of InstagramProfile objects that satisfied criteria and were saved.
        rejected_profiles: Count of fetched profiles that failed filter criteria evaluation.
        failed_profiles: Count of candidate handles that encountered crawl/fetch errors.
        skipped_existing: Count of candidates already present in storage and bypassed.
        stopped_by_rate_limit: True if the crawl session encountered a rate limit block.
    """

    discovered_candidates: int

    checked_profiles: int

    matched_profiles: tuple[
        InstagramProfile,
        ...,
    ]

    rejected_profiles: int

    failed_profiles: int

    skipped_existing: int

    stopped_by_rate_limit: bool


class InstagramShopDiscoveryEngine:
    """Progressive automatic Instagram shop discovery engine.

    Instead of collecting a fixed candidate pool prior to crawling, queries are executed
    sequentially and discovered candidates are fetched, classified, and filtered immediately.

    Pipeline:
        search query -> candidate batch -> fetch profile -> classify -> filter -> persist

    Discovery stops when:
    - target_results matches are saved
    - max_candidates evaluation budget is reached
    - search queries are exhausted
    - crawl-session safety stops the process (rate limits)
    """

    # Expanded category-specific search term templates for web search candidate discovery
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
            '"cosmetics shop" iran',
            '"beauty shop" iran',
            '"skincare shop" iran',
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
            '"clothing shop" iran',
            '"fashion store" iran',
        ),
        ProfileCategory.FASHION: (
            '"فشن" فروشگاه',
            '"استایل" فروشگاه',
            '"استایل" خرید',
            '"فشن" خرید',
            '"fashion shop" iran',
            '"fashion store" iran',
            '"style shop" iran',
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
            '"home appliance" iran instagram',
            '"home decor shop" iran',
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
            '"accessories shop" iran',
            '"jewelry shop" iran',
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
            '"toy store" iran',
            '"toy shop" iran',
        ),
    }

    def __init__(
        self,
        *,
        source: DiscoverySource,
        storage: JsonProfileStorage,
        crawl_session: InstagramCrawlSession | None = None,
        shop_classifier: ShopClassifier | None = None,
        category_classifier: CategoryClassifier | None = None,
        link_classifier: LinkClassifier | None = None,
        filter_engine: ProfileFilterEngine | None = None,
    ) -> None:
        """Initializes the progressive discovery engine with sources, storage, and classifiers."""
        self._source = source
        self._storage = storage

        self._crawl_session = crawl_session or InstagramCrawlSession()

        self._shop_classifier = shop_classifier or ShopClassifier()

        self._category_classifier = category_classifier or CategoryClassifier()

        self._link_classifier = link_classifier or LinkClassifier()

        self._filter_engine = filter_engine or ProfileFilterEngine()

    def discover(
        self,
        criteria: DiscoveryCriteria,
    ) -> DiscoveryResult:
        """Executes progressive shop discovery sequentially across queries until criteria are satisfied.

        Args:
            criteria: DiscoveryCriteria instance specifying search targets and constraints.

        Returns:
            A DiscoveryResult summary containing matched profiles and telemetry metrics.
        """
        # Step 1: Build deduplicated web search queries based on criteria
        queries = self._build_queries(criteria)

        # Cache existing stored usernames to skip redundant crawling
        stored_usernames = {
            profile.username.lower() for profile in self._storage.get_all()
        }

        # Configure profile filter criteria
        filter_criteria = ProfileFilter(
            is_shop=True,
            category=criteria.category,
            min_followers=(criteria.min_followers),
            max_followers=(criteria.max_followers),
            min_shop_score=(criteria.min_shop_score),
        )

        matches: list[InstagramProfile] = []

        seen_candidates: set[str] = set()

        discovered_candidates = 0
        checked_profiles = 0
        rejected_profiles = 0
        failed_profiles = 0
        skipped_existing = 0
        stopped_by_rate_limit = False

        # Step 2: Progressively iterate search queries and process candidates on the fly
        try:
            with self._crawl_session:
                for query in queries:
                    if len(matches) >= criteria.target_results:
                        break

                    if discovered_candidates >= criteria.max_candidates:
                        break

                    remaining_candidate_budget = (
                        criteria.max_candidates - discovered_candidates
                    )

                    query_limit = min(
                        50,
                        remaining_candidate_budget,
                    )

                    if query_limit <= 0:
                        break

                    candidates = self._source.discover(
                        query=query,
                        limit=query_limit,
                    )

                    for username in candidates:
                        if len(matches) >= criteria.target_results:
                            break

                        if discovered_candidates >= criteria.max_candidates:
                            break

                        normalized_username = username.strip().lstrip("@").lower()

                        if not normalized_username:
                            continue

                        if normalized_username in seen_candidates:
                            continue

                        seen_candidates.add(normalized_username)

                        discovered_candidates += 1

                        # Skip handle if already present in storage
                        if normalized_username in stored_usernames:
                            skipped_existing += 1
                            continue

                        print(
                            f"Checking @{normalized_username} "
                            f"({discovered_candidates}/{criteria.max_candidates})..."
                        )

                        # Step 3: Fetch public profile metadata
                        try:
                            raw = self._crawl_session.fetch(normalized_username)

                        except CrawlSessionStoppedError:
                            stopped_by_rate_limit = True
                            break

                        except ProfileFetchError as exc:
                            failed_profiles += 1

                            print(f"   fetch failed: {exc}")

                            continue

                        checked_profiles += 1

                        profile = self._profile_from_raw(raw)

                        # Step 4: Run classifiers (shop, category, link)
                        profile = apply_classifications(
                            profile,
                            shop_classifier=(self._shop_classifier),
                            category_classifier=(self._category_classifier),
                            link_classifier=(self._link_classifier),
                        )

                        # Step 5: Evaluate against filter criteria
                        if not self._filter_engine.matches(
                            profile=profile,
                            criteria=filter_criteria,
                        ):
                            rejected_profiles += 1

                            print(
                                "   rejected"
                                f" | followers={profile.followers_count:,}"
                                f" | category={profile.category.value}"
                                f" | is_shop={profile.is_shop}"
                                f" | score={self._score_label(profile)}"
                            )

                            continue

                        # Step 6: Persist matching profile
                        self._storage.save(profile)

                        stored_usernames.add(profile.username.lower())

                        matches.append(profile)

                        print(
                            "   MATCH"
                            f" | followers={profile.followers_count:,}"
                            f" | category={profile.category.value}"
                            f" | score={self._score_label(profile)}"
                            f" | total={len(matches)}/{criteria.target_results}"
                        )

                    if stopped_by_rate_limit:
                        break

        except CrawlSessionStoppedError:
            stopped_by_rate_limit = True

        return DiscoveryResult(
            discovered_candidates=(discovered_candidates),
            checked_profiles=(checked_profiles),
            matched_profiles=tuple(matches),
            rejected_profiles=(rejected_profiles),
            failed_profiles=(failed_profiles),
            skipped_existing=(skipped_existing),
            stopped_by_rate_limit=(stopped_by_rate_limit),
        )

    @staticmethod
    def _profile_from_raw(
        raw: RawProfileData,
    ) -> InstagramProfile:
        """Maps a raw scraped profile data object to an InstagramProfile domain model."""
        return InstagramProfile(
            username=raw.username,
            profile_url=("https://www.instagram.com/" f"{raw.username}/"),
            display_name=(raw.display_name),
            bio=raw.bio,
            external_links=(raw.external_links),
            followers_count=(raw.followers_count),
            following_count=(raw.following_count),
            posts_count=(raw.posts_count),
            is_public=raw.is_public,
        )

    @staticmethod
    def _score_label(
        profile: InstagramProfile,
    ) -> str:
        """Formats a profile's shop score as a percentage string or placeholder."""
        if profile.shop_score is None:
            return "-"

        return f"{profile.shop_score:.0%}"

    def _build_queries(
        self,
        criteria: DiscoveryCriteria,
    ) -> tuple[str, ...]:
        """Builds deduplicated search queries based on target categories and additional terms."""
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
