"""Automatic discovery pipeline for identifying and storing Instagram shop profiles."""

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
from app.storage.json_storage import (
    JsonProfileStorage,
)


@dataclass(
    frozen=True,
    slots=True,
)
class DiscoveryCriteria:
    """Configurable constraints and parameters governing a shop discovery run.

    Attributes:
        category: Target ProfileCategory to search for (None searches across all categories).
        target_results: Maximum number of matching shop profiles to discover and save.
        min_followers: Optional minimum follower count threshold.
        max_followers: Optional maximum follower count threshold.
        min_shop_score: Minimum shop confidence score required to match (0.0 to 1.0).
        additional_query: Optional search keyword or phrase appended to search queries.
        max_candidates: Maximum number of candidate usernames to retrieve from web search.
    """

    category: ProfileCategory | None

    target_results: int = 20

    min_followers: int | None = None

    max_followers: int | None = None

    min_shop_score: float = 0.60

    additional_query: str | None = None

    max_candidates: int = 200

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
    """Telemetry and profile collection outputs returned by a discovery run.

    Attributes:
        discovered_candidates: Total count of candidate handles obtained from discovery sources.
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
    """Automatic shop discovery pipeline.

    Pipeline:
        search queries
            ↓
        candidate usernames
            ↓
        public Instagram fetch
            ↓
        shop/category classification
            ↓
        follower/category/shop filtering
            ↓
        save matching shops
    """

    # Category-specific search term templates for web search candidate discovery
    _CATEGORY_SEARCH_TERMS: dict[
        ProfileCategory,
        tuple[str, ...],
    ] = {
        ProfileCategory.BEAUTY: (
            '"فروشگاه آرایشی"',
            '"لوازم آرایشی"',
            '"میکاپ" "فروشگاه"',
            '"beauty shop"',
        ),
        ProfileCategory.CLOTHING: (
            '"فروشگاه لباس"',
            '"فروشگاه پوشاک"',
            '"لباس زیر" فروشگاه',
            '"clothing shop"',
        ),
        ProfileCategory.FASHION: (
            '"فشن" فروشگاه',
            '"استایل" فروشگاه',
            '"fashion shop"',
        ),
        ProfileCategory.HOME: (
            '"فروشگاه لوازم خانگی"',
            '"لوازم خانه" فروشگاه',
            '"لوازم آشپزخانه" فروشگاه',
        ),
        ProfileCategory.ACCESSORIES: (
            '"فروشگاه اکسسوری"',
            '"بدلیجات" فروشگاه',
            '"زیورآلات" فروشگاه',
            '"accessories shop"',
        ),
        ProfileCategory.TOYS: (
            '"فروشگاه اسباب بازی"',
            '"اسباب بازی" خرید',
            '"اسباب بازی" ارسال',
            '"toy store"',
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
        """Initializes the discovery engine with data sources, storage, and classification tools."""
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
        """Executes the full shop discovery pipeline according to the provided criteria.

        Args:
            criteria: DiscoveryCriteria instance specifying search targets and constraints.

        Returns:
            A DiscoveryResult summary containing matched profiles and telemetry counters.
        """
        # Step 1: Construct web search queries based on category and optional phrases
        queries = self._build_queries(criteria)

        # Step 2: Query candidate source for raw Instagram handles
        candidates = self._discover_candidates(
            queries=queries,
            max_candidates=(criteria.max_candidates),
        )

        # Pre-load existing usernames from storage to avoid re-fetching known profiles
        stored_usernames = {
            profile.username.lower() for profile in self._storage.get_all()
        }

        # Configure profile filter engine criteria
        filter_criteria = ProfileFilter(
            is_shop=True,
            category=criteria.category,
            min_followers=(criteria.min_followers),
            max_followers=(criteria.max_followers),
            min_shop_score=(criteria.min_shop_score),
        )

        matches: list[InstagramProfile] = []

        checked_profiles = 0
        rejected_profiles = 0
        failed_profiles = 0
        skipped_existing = 0
        stopped_by_rate_limit = False

        # Step 3: Iterate candidates within a managed crawl session
        try:
            with self._crawl_session:
                for username in candidates:
                    # Halt processing if desired target count is reached
                    if len(matches) >= criteria.target_results:
                        break

                    # Skip candidate if profile is already stored locally
                    if username.lower() in stored_usernames:
                        skipped_existing += 1
                        continue

                    # Fetch raw public profile metadata
                    try:
                        raw = self._crawl_session.fetch(username)

                    except CrawlSessionStoppedError:
                        stopped_by_rate_limit = True
                        break

                    except ProfileFetchError:
                        failed_profiles += 1
                        continue

                    checked_profiles += 1

                    # Map raw profile data to standard InstagramProfile domain model
                    profile = InstagramProfile(
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

                    # Step 4: Run classifiers (shop, category, external link)
                    profile = apply_classifications(
                        profile,
                        shop_classifier=(self._shop_classifier),
                        category_classifier=(self._category_classifier),
                        link_classifier=(self._link_classifier),
                    )

                    # Step 5: Evaluate profile against filter criteria
                    if not self._filter_engine.matches(
                        profile=profile,
                        criteria=filter_criteria,
                    ):
                        rejected_profiles += 1
                        continue

                    # Step 6: Persist matching shop profile to storage
                    self._storage.save(profile)

                    stored_usernames.add(profile.username.lower())

                    matches.append(profile)

        except CrawlSessionStoppedError:
            stopped_by_rate_limit = True

        return DiscoveryResult(
            discovered_candidates=len(candidates),
            checked_profiles=(checked_profiles),
            matched_profiles=tuple(matches),
            rejected_profiles=(rejected_profiles),
            failed_profiles=(failed_profiles),
            skipped_existing=(skipped_existing),
            stopped_by_rate_limit=(stopped_by_rate_limit),
        )

    def _build_queries(
        self,
        criteria: DiscoveryCriteria,
    ) -> tuple[str, ...]:
        """Builds deduplicated search engine queries based on discovery category and additional terms."""
        additional = (
            criteria.additional_query.strip() if criteria.additional_query else ""
        )

        categories: tuple[
            ProfileCategory,
            ...,
        ]

        # Target specific category or expand across all non-UNKNOWN categories
        if criteria.category is None:
            categories = tuple(
                category
                for category in ProfileCategory
                if category != ProfileCategory.UNKNOWN
            )

        else:
            categories = (criteria.category,)

        queries: list[str] = []

        seen: set[str] = set()

        for category in categories:
            category_terms = self._CATEGORY_SEARCH_TERMS.get(
                category,
                (f'"{category.value}" ' '"فروشگاه"',),
            )

            for term in category_terms:
                parts = [
                    "site:instagram.com",
                    term,
                ]

                if additional:
                    parts.append(additional)

                query = " ".join(parts)

                if query in seen:
                    continue

                seen.add(query)

                queries.append(query)

        return tuple(queries)

    def _discover_candidates(
        self,
        *,
        queries: tuple[str, ...],
        max_candidates: int,
    ) -> list[str]:
        """Queries the candidate source across generated queries to collect unique Instagram handles."""
        candidates: list[str] = []

        seen: set[str] = set()

        if not queries:
            return []

        # Calculate per-query candidate allocation limit
        per_query_limit = max(
            5,
            (max_candidates + len(queries) - 1) // len(queries),
        )

        for query in queries:
            remaining = max_candidates - len(candidates)

            if remaining <= 0:
                break

            discovered = self._source.discover(
                query=query,
                limit=min(
                    per_query_limit,
                    remaining,
                ),
            )

            for username in discovered:
                normalized = username.strip().lstrip("@").lower()

                if not normalized:
                    continue

                if normalized in seen:
                    continue

                seen.add(normalized)

                candidates.append(normalized)

                if len(candidates) >= max_candidates:
                    break

        return candidates
