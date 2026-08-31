from __future__ import annotations

import re
import time
from collections.abc import Callable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app.discovery.base import DiscoverySource


class DirectoryDiscoverySource(DiscoverySource):
    """
    Discover Instagram shop usernames from public directory/list/article pages.

    Extracts candidates from:
    - direct instagram.com/<username> links
    - explicit @username mentions
    - strongly-labelled text such as:
        Instagram: username
        اینستاگرام: username
        آدرس پیج: username

    No Instagram login or access-control bypass is used.
    """

    _USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._]{2,30}$")

    _AT_USERNAME_PATTERN = re.compile(
        r"(?<![A-Za-z0-9._])" r"@(?P<username>[A-Za-z0-9._]{2,30})"
    )

    _INSTAGRAM_URL_PATTERN = re.compile(
        r"https?://(?:www\.)?instagram\.com/" r"(?P<username>[A-Za-z0-9._]{2,30})",
        flags=re.IGNORECASE,
    )

    _LABELLED_USERNAME_PATTERNS = (
        re.compile(
            r"(?:"
            r"اینستاگرام|"
            r"آدرس\s+اینستاگرام|"
            r"پیج\s+اینستاگرام|"
            r"آدرس\s+پیج|"
            r"نام\s+پیج|"
            r"instagram"
            r")"
            r"\s*[:：\-–—]\s*"
            r"@?(?P<username>[A-Za-z0-9._]{2,30})",
            flags=re.IGNORECASE,
        ),
    )

    _BLOCKED_INSTAGRAM_SEGMENTS = {
        "about",
        "accounts",
        "api",
        "challenge",
        "developer",
        "developers",
        "direct",
        "directory",
        "explore",
        "legal",
        "oauth",
        "p",
        "popular",
        "privacy",
        "reel",
        "reels",
        "stories",
        "web",
    }

    # Common English words accidentally found after labels like "Instagram".
    _BLOCKED_USERNAMES = {
        "about",
        "account",
        "accounts",
        "ads",
        "and",
        "best",
        "blog",
        "click",
        "contact",
        "engagement",
        "facebook",
        "follow",
        "followers",
        "following",
        "here",
        "home",
        "influencer",
        "instagram",
        "like",
        "likes",
        "link",
        "more",
        "only",
        "page",
        "post",
        "posts",
        "profile",
        "read",
        "reel",
        "reels",
        "shop",
        "social",
        "story",
        "stories",
        "store",
        "telegram",
        "twitter",
        "website",
        "whatsapp",
        "youtube",
    }

    _GENERAL_SEEDS = (
        "https://inbo.ir/best-instagram-store-pages/",
        "https://myfxzone.com/best-selling-instagram-pages-in-iran/",
    )

    _BEAUTY_SEEDS = (
        "https://kallaxcargo.com/blog/best-Instagram-cosmetics-page",
        "https://hircana.com/blog/top-cosmetic-Instagram-pages-in-this-year",
        "https://mobinashop.ir/the-best-cosmetics-stores-in-iran/",
    )

    _CLOTHING_SEEDS = (
        "https://najvafact.com/20823/best-clothing-pages-on-instagram/",
        "https://modixo.ir/blog/best-clothing-page-and-online-store",
        "https://parsisocial.com/blog/best-instagram-clothing-sales-pages/",
        "https://khoobo.com/instagram-clothing-sales-pages/",
        "https://hircana.com/blog/top-online-shopping-stores",
    )

    # Intentionally empty until we have good toy-shop directory pages.
    #
    # The previous SocialVeins seed was removed because it was an
    # influencer analytics page and produced unrelated accounts.
    _TOYS_SEEDS = (
        "https://behtarin-dar-qom.ir/best-toy-stores-qom/",
        "https://bestinmashhad.com/mashhad-toy-store/",
        "https://bestinmashhad.com/instagram-pages-mashhad-toy-store/",
        "https://locfa.ir/toy-store-in-toy-toy/",
    )
    _INTERNAL_LINK_HINTS = (
        "instagram",
        "اینستاگرام",
        "shop",
        "store",
        "فروشگاه",
        "پیج",
        "best",
        "top",
        "بهترین",
        "برتر",
        "clothing",
        "fashion",
        "beauty",
        "cosmetic",
        "toy",
        "لباس",
        "پوشاک",
        "آرایشی",
        "اسباب",
    )

    _CATEGORY_KEYWORDS = {
        "beauty": (
            "beauty",
            "cosmetic",
            "cosmetics",
            "آرایشی",
            "آرایش",
            "بهداشتی",
            "میکاپ",
            "پوست",
        ),
        "clothing": (
            "clothing",
            "fashion",
            "dress",
            "wear",
            "لباس",
            "پوشاک",
            "مانتو",
            "مزون",
            "شومیز",
            "زنانه",
            "مردانه",
        ),
        "toys": (
            "toy",
            "toys",
            "اسباب بازی",
            "اسباب‌بازی",
            "اسباببازی",
            "عروسک",
            "لگو",
            "بازی فکری",
        ),
        "accessories": (
            "accessory",
            "accessories",
            "اکسسوری",
            "زیورآلات",
            "بدلیجات",
            "کیف",
            "کفش",
        ),
        "home": (
            "home",
            "decor",
            "decoration",
            "خانه",
            "دکور",
            "دکوراسیون",
            "لوازم خانگی",
        ),
    }

    def __init__(
        self,
        *,
        timeout_seconds: float = 12.0,
        max_pages_per_seed: int = 2,
        request_delay_seconds: float = 0.4,
        sleeper: Callable[[float], None] = time.sleep,
        seed_urls: tuple[str, ...] | None = None,
    ) -> None:
        self._timeout_seconds = timeout_seconds

        self._max_pages_per_seed = max(
            1,
            max_pages_per_seed,
        )

        self._request_delay_seconds = max(
            0.0,
            request_delay_seconds,
        )

        self._sleeper = sleeper
        self._seed_urls_override = seed_urls

        self._session = requests.Session()

        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/131.0 Safari/537.36"
                ),
                "Accept": ("text/html," "application/xhtml+xml"),
                "Accept-Language": ("fa-IR,fa;q=0.9," "en-US;q=0.8,en;q=0.7"),
            }
        )

    def discover(
        self,
        *,
        query: str,
        limit: int,
    ) -> list[str]:
        if limit <= 0:
            return []

        seeds = self._select_seed_urls(query)

        results: list[str] = []
        seen_usernames: set[str] = set()
        visited_urls: set[str] = set()

        for seed_url in seeds:
            if len(results) >= limit:
                break

            self._crawl_seed(
                seed_url=seed_url,
                query=query,
                limit=limit,
                output=results,
                seen_usernames=seen_usernames,
                visited_urls=visited_urls,
            )

        return results

    def _crawl_seed(
        self,
        *,
        seed_url: str,
        query: str,
        limit: int,
        output: list[str],
        seen_usernames: set[str],
        visited_urls: set[str],
    ) -> None:
        queue: list[str] = [seed_url]

        pages_checked = 0

        seed_host = self._hostname(seed_url)

        while (
            queue and pages_checked < self._max_pages_per_seed and len(output) < limit
        ):
            url = queue.pop(0)

            normalized_url = url.rstrip("/")

            if normalized_url in visited_urls:
                continue

            visited_urls.add(normalized_url)

            html = self._fetch_html(url)

            if not html:
                continue

            pages_checked += 1

            usernames = self._extract_instagram_usernames(html)

            for username in usernames:
                if username in seen_usernames:
                    continue

                seen_usernames.add(username)

                output.append(username)

                if len(output) >= limit:
                    return

            if pages_checked < self._max_pages_per_seed:
                related_pages = self._extract_related_internal_pages(
                    html=html,
                    current_url=url,
                    root_host=seed_host,
                    query=query,
                )

                for related_url in related_pages:
                    key = related_url.rstrip("/")

                    if key in visited_urls:
                        continue

                    if related_url in queue:
                        continue

                    queue.append(related_url)

            self._sleep()

    def _select_seed_urls(
        self,
        query: str,
    ) -> tuple[str, ...]:
        if self._seed_urls_override is not None:
            return self._dedupe_urls(self._seed_urls_override)

        normalized_query = self._normalize_text(query)

        selected: list[str] = []

        category_found = False

        if self._contains_any(
            normalized_query,
            self._CATEGORY_KEYWORDS["beauty"],
        ):
            selected.extend(self._BEAUTY_SEEDS)

            category_found = True

        if self._contains_any(
            normalized_query,
            self._CATEGORY_KEYWORDS["clothing"],
        ):
            selected.extend(self._CLOTHING_SEEDS)

            category_found = True

        if self._contains_any(
            normalized_query,
            self._CATEGORY_KEYWORDS["toys"],
        ):
            selected.extend(self._TOYS_SEEDS)

            category_found = True

        if self._contains_any(
            normalized_query,
            self._CATEGORY_KEYWORDS["accessories"],
        ):
            selected.extend(self._CLOTHING_SEEDS)

            category_found = True

        if self._contains_any(
            normalized_query,
            self._CATEGORY_KEYWORDS["home"],
        ):
            selected.extend(self._GENERAL_SEEDS)

            category_found = True

        if not category_found:
            selected.extend(self._BEAUTY_SEEDS)

            selected.extend(self._CLOTHING_SEEDS)

        # General pages are useful for all categories, but only after
        # the high-precision category-specific seeds.
        selected.extend(self._GENERAL_SEEDS)

        return self._dedupe_urls(tuple(selected))

    def _fetch_html(
        self,
        url: str,
    ) -> str:
        try:
            response = self._session.get(
                url,
                timeout=self._timeout_seconds,
                allow_redirects=True,
            )

        except requests.RequestException:
            return ""

        if response.status_code != 200:
            return ""

        content_type = response.headers.get(
            "content-type",
            "",
        ).lower()

        if "text/html" not in content_type and "application/xhtml" not in content_type:
            return ""

        return response.text

    @classmethod
    def _extract_instagram_usernames(
        cls,
        html: str,
    ) -> list[str]:
        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        usernames: list[str] = []
        seen: set[str] = set()

        def add(
            raw_username: str,
        ) -> None:
            username = raw_username.strip().lstrip("@").lower()

            if not cls._is_valid_username(username):
                return

            if username in seen:
                return

            seen.add(username)

            usernames.append(username)

        # 1. Direct Instagram <a href=""> links.
        for anchor in soup.find_all(
            "a",
            href=True,
        ):
            href = str(anchor.get("href") or "").strip()

            username = cls._instagram_username_from_url(href)

            if username is not None:
                add(username)

        # 2. Instagram URLs embedded directly in HTML / JSON / JS.
        for match in cls._INSTAGRAM_URL_PATTERN.finditer(html):
            add(match.group("username"))

        text = soup.get_text(
            "\n",
            strip=True,
        )

        # 3. Explicit @username mentions.
        for match in cls._AT_USERNAME_PATTERN.finditer(text):
            add(match.group("username"))

        # 4. Strongly labelled username text.
        #
        # Requiring a separator such as ":" dramatically reduces
        # false positives such as:
        #
        # Instagram engagement
        # Instagram stories
        # Instagram post
        for pattern in cls._LABELLED_USERNAME_PATTERNS:
            for match in pattern.finditer(text):
                add(match.group("username"))

        return usernames

    def _extract_related_internal_pages(
        self,
        *,
        html: str,
        current_url: str,
        root_host: str,
        query: str,
    ) -> list[str]:
        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        candidates: list[
            tuple[
                int,
                str,
            ]
        ] = []

        seen: set[str] = set()

        normalized_query = self._normalize_text(query)

        query_tokens = {
            token
            for token in re.findall(
                r"[A-Za-z0-9_\u0600-\u06ff]+",
                normalized_query,
            )
            if len(token) >= 3
        }

        for anchor in soup.find_all(
            "a",
            href=True,
        ):
            raw_href = str(anchor.get("href") or "").strip()

            if not raw_href:
                continue

            absolute = urljoin(
                current_url,
                raw_href,
            )

            parsed = urlparse(absolute)

            hostname = (parsed.hostname or "").lower()

            hostname = hostname.removeprefix("www.")

            if hostname != root_host:
                continue

            if parsed.scheme not in {
                "http",
                "https",
            }:
                continue

            key = absolute.rstrip("/")

            if not key or key in seen:
                continue

            text = anchor.get_text(
                " ",
                strip=True,
            )

            searchable = f"{parsed.path} {text}"

            normalized_searchable = self._normalize_text(searchable)

            score = 0

            for hint in self._INTERNAL_LINK_HINTS:
                if self._normalize_text(hint) in normalized_searchable:
                    score += 2

            for token in query_tokens:
                if token in normalized_searchable:
                    score += 3

            if score <= 0:
                continue

            seen.add(key)

            candidates.append(
                (
                    score,
                    absolute,
                )
            )

        candidates.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        return [url for _, url in candidates[:10]]

    @classmethod
    def _instagram_username_from_url(
        cls,
        url: str,
    ) -> str | None:
        if not url:
            return None

        if url.startswith("//"):
            url = f"https:{url}"

        if not url.startswith(
            (
                "http://",
                "https://",
            )
        ):
            return None

        parsed = urlparse(url)

        hostname = (parsed.hostname or "").lower()

        if hostname not in {
            "instagram.com",
            "www.instagram.com",
        }:
            return None

        parts = [part for part in parsed.path.split("/") if part]

        if len(parts) != 1:
            return None

        username = parts[0].strip().lower()

        if not cls._is_valid_username(username):
            return None

        return username

    @classmethod
    def _is_valid_username(
        cls,
        username: str,
    ) -> bool:
        normalized = username.strip().lstrip("@").lower()

        if not normalized:
            return False

        if normalized in cls._BLOCKED_INSTAGRAM_SEGMENTS:
            return False

        if normalized in cls._BLOCKED_USERNAMES:
            return False

        if cls._USERNAME_PATTERN.fullmatch(normalized) is None:
            return False

        # Do not accept punctuation-only/numeric garbage such as:
        # 12
        # 1.
        # 4.
        #
        # For shop discovery, requiring at least one ASCII letter is
        # a useful precision trade-off.
        if (
            re.search(
                r"[A-Za-z]",
                normalized,
            )
            is None
        ):
            return False

        if normalized.startswith("."):
            return False

        if normalized.endswith("."):
            return False

        if ".." in normalized:
            return False

        return True

    @staticmethod
    def _contains_any(
        text: str,
        terms: tuple[str, ...],
    ) -> bool:
        return any(
            DirectoryDiscoverySource._normalize_text(term) in text for term in terms
        )

    @staticmethod
    def _normalize_text(
        value: str,
    ) -> str:
        translation = str.maketrans(
            {
                "ي": "ی",
                "ى": "ی",
                "ك": "ک",
                "\u200c": " ",
                "\u200f": "",
                "\u200e": "",
            }
        )

        normalized = value.translate(translation).casefold()

        normalized = re.sub(
            r"\s+",
            " ",
            normalized,
        )

        return normalized.strip()

    @staticmethod
    def _hostname(
        url: str,
    ) -> str:
        parsed = urlparse(url)

        return (parsed.hostname or "").lower().removeprefix("www.")

    @staticmethod
    def _dedupe_urls(
        urls: tuple[str, ...],
    ) -> tuple[str, ...]:
        result: list[str] = []
        seen: set[str] = set()

        for url in urls:
            normalized = url.strip()

            if not normalized:
                continue

            key = normalized.rstrip("/")

            if key in seen:
                continue

            seen.add(key)

            result.append(normalized)

        return tuple(result)

    def _sleep(
        self,
    ) -> None:
        if self._request_delay_seconds > 0:
            self._sleeper(self._request_delay_seconds)
