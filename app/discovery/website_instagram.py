from __future__ import annotations

import base64
import re
import time
from collections.abc import Callable
from urllib.parse import (
    parse_qs,
    urljoin,
    urlparse,
)

import requests
from bs4 import BeautifulSoup

from app.discovery.base import DiscoverySource


class WebsiteInstagramLinkDiscoverySource(DiscoverySource):
    """
    Discover Instagram usernames indirectly through public shop websites.

    Flow:
        category/search phrase
        -> Bing finds relevant shop websites
        -> crawl shop homepage/contact/about
        -> extract instagram.com/<username>
        -> return usernames

    Instagram itself is not used for discovery here.
    """

    _BING_URL = "https://www.bing.com/search"

    _INSTAGRAM_USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9._]{1,30}$")

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

    # Large/general sites are usually poor discovery seeds.
    _BLOCKED_WEBSITE_HOSTS = {
        "bing.com",
        "www.bing.com",
        "google.com",
        "www.google.com",
        "play.google.com",
        "instagram.com",
        "www.instagram.com",
        "facebook.com",
        "www.facebook.com",
        "youtube.com",
        "www.youtube.com",
        "tiktok.com",
        "www.tiktok.com",
        # General Iranian marketplaces/directories.
        "digikala.com",
        "www.digikala.com",
        "torob.com",
        "www.torob.com",
        "basalam.com",
        "www.basalam.com",
        "emalls.ir",
        "www.emalls.ir",
        "technolife.ir",
        "www.technolife.ir",
        "cafebazaar.ir",
        "www.cafebazaar.ir",
    }

    _INTERNAL_PATH_HINTS = (
        "contact",
        "contact-us",
        "about",
        "about-us",
        "social",
        "تماس",
        "درباره",
        "شبکه",
    )

    _SEARCH_NOISE_PATTERN = re.compile(
        r"\bsite\s*:\s*instagram\.com\b",
        flags=re.IGNORECASE,
    )

    def __init__(
        self,
        *,
        timeout_seconds: float = 12.0,
        search_pages: int = 3,
        max_sites_per_query: int = 30,
        max_internal_pages_per_site: int = 3,
        request_delay_seconds: float = 0.5,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._search_pages = search_pages
        self._max_sites_per_query = max_sites_per_query
        self._max_internal_pages_per_site = max_internal_pages_per_site
        self._request_delay_seconds = request_delay_seconds
        self._sleeper = sleeper

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
                "Accept-Language": ("fa,en-US;q=0.8,en;q=0.7"),
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

        queries = self._build_search_queries(query)

        usernames: list[str] = []
        seen_usernames: set[str] = set()
        seen_websites: set[str] = set()

        for search_query in queries:
            if len(usernames) >= limit:
                break

            websites = self._discover_websites(query=search_query)

            for website in websites:
                if len(usernames) >= limit:
                    break

                website_key = self._website_key(website)

                if not website_key or website_key in seen_websites:
                    continue

                seen_websites.add(website_key)

                found = self._discover_from_website(website)

                for username in found:
                    if username in seen_usernames:
                        continue

                    seen_usernames.add(username)
                    usernames.append(username)

                    if len(usernames) >= limit:
                        break

                if self._request_delay_seconds > 0:
                    self._sleeper(self._request_delay_seconds)

        return usernames

    def _build_search_queries(
        self,
        query: str,
    ) -> list[str]:
        phrase = self._clean_original_query(query)

        if not phrase:
            phrase = "فروشگاه آنلاین"

        negative_sites = (
            "-site:digikala.com "
            "-site:torob.com "
            "-site:basalam.com "
            "-site:emalls.ir "
            "-site:technolife.ir "
            "-site:cafebazaar.ir"
        )

        candidates = [
            f'{phrase} "اینستاگرام" {negative_sites}',
            f'{phrase} "پیج اینستاگرام" {negative_sites}',
            f'{phrase} "فروشگاه اینترنتی" instagram {negative_sites}',
            f'{phrase} "تماس با ما" instagram {negative_sites}',
            f"{phrase} instagram فروشگاه {negative_sites}",
        ]

        result: list[str] = []
        seen: set[str] = set()

        for candidate in candidates:
            normalized = re.sub(
                r"\s+",
                " ",
                candidate,
            ).strip()

            if normalized in seen:
                continue

            seen.add(normalized)
            result.append(normalized)

        return result

    @classmethod
    def _clean_original_query(
        cls,
        query: str,
    ) -> str:
        cleaned = cls._SEARCH_NOISE_PATTERN.sub(
            "",
            query,
        )

        cleaned = cleaned.replace(
            '"',
            " ",
        )

        cleaned = re.sub(
            r"\s+",
            " ",
            cleaned,
        ).strip()

        return cleaned

    def _discover_websites(
        self,
        *,
        query: str,
    ) -> list[str]:
        websites: list[str] = []
        seen_hosts: set[str] = set()

        for page_index in range(self._search_pages):
            if len(websites) >= self._max_sites_per_query:
                break

            first = (page_index * 10) + 1

            html = self._fetch_bing(
                query=query,
                first=first,
            )

            if not html:
                continue

            soup = BeautifulSoup(
                html,
                "html.parser",
            )

            results = soup.select("li.b_algo")

            for result in results:
                anchor = result.select_one("h2 a[href]")

                if anchor is None:
                    continue

                href = str(anchor.get("href") or "").strip()

                destination = self._decode_bing_result_url(href)

                if not destination:
                    continue

                if not self._is_candidate_website(destination):
                    continue

                if not self._result_looks_relevant(
                    result=result,
                    search_query=query,
                ):
                    continue

                parsed = urlparse(destination)

                hostname = (parsed.hostname or "").lower()

                hostname_key = hostname.removeprefix("www.")

                if not hostname_key or hostname_key in seen_hosts:
                    continue

                seen_hosts.add(hostname_key)

                root_url = f"{parsed.scheme}://" f"{parsed.netloc}/"

                websites.append(root_url)

                if len(websites) >= self._max_sites_per_query:
                    break

            if page_index + 1 < self._search_pages and self._request_delay_seconds > 0:
                self._sleeper(self._request_delay_seconds)

        return websites

    @staticmethod
    def _result_looks_relevant(
        *,
        result,
        search_query: str,
    ) -> bool:
        text = result.get_text(
            " ",
            strip=True,
        ).casefold()

        if not text:
            return False

        # These terms indicate an actual shop/business page.
        commercial_terms = (
            "فروشگاه",
            "خرید",
            "محصول",
            "سفارش",
            "shop",
            "store",
        )

        if not any(term in text for term in commercial_terms):
            return False

        # Pull useful Persian category words from the original query.
        ignored = {
            "site",
            "instagram",
            "com",
            "اینستاگرام",
            "پیج",
            "فروشگاه",
            "آنلاین",
            "اینترنتی",
            "تماس",
            "با",
            "ما",
            "the",
            "and",
        }

        query_terms = {
            token.casefold()
            for token in re.findall(
                r"[\wآ-ی]+",
                search_query,
            )
            if len(token) >= 3 and token.casefold() not in ignored
        }

        # If we have meaningful category words, require at least one.
        if query_terms:
            return any(term in text for term in query_terms)

        return True

    def _fetch_bing(
        self,
        *,
        query: str,
        first: int,
    ) -> str:
        try:
            response = self._session.get(
                self._BING_URL,
                params={
                    "q": query,
                    "first": first,
                    "count": 10,
                    "setlang": "fa",
                },
                timeout=self._timeout_seconds,
            )

        except requests.RequestException:
            return ""

        if response.status_code != 200:
            return ""

        return response.text

    @classmethod
    def _decode_bing_result_url(
        cls,
        url: str,
    ) -> str | None:
        parsed = urlparse(url)

        hostname = (parsed.hostname or "").lower()

        if hostname not in {
            "bing.com",
            "www.bing.com",
        }:
            return url

        query = parse_qs(parsed.query)

        values = query.get("u")

        if not values:
            return None

        encoded = values[0]

        if encoded.startswith("a1"):
            encoded = encoded[2:]

        try:
            padding = "=" * (-len(encoded) % 4)

            decoded = (
                base64.urlsafe_b64decode(encoded + padding)
                .decode(
                    "utf-8",
                    errors="ignore",
                )
                .strip()
            )

        except Exception:
            return None

        if not decoded.startswith(
            (
                "http://",
                "https://",
            )
        ):
            return None

        return decoded

    @classmethod
    def _is_candidate_website(
        cls,
        url: str,
    ) -> bool:
        parsed = urlparse(url)

        if parsed.scheme not in {
            "http",
            "https",
        }:
            return False

        hostname = (parsed.hostname or "").lower()

        if not hostname:
            return False

        if hostname in cls._BLOCKED_WEBSITE_HOSTS:
            return False

        normalized_hostname = hostname.removeprefix("www.")

        for blocked in cls._BLOCKED_WEBSITE_HOSTS:
            normalized_blocked = blocked.removeprefix("www.")

            if normalized_hostname == normalized_blocked:
                return False

        return True

    def _discover_from_website(
        self,
        root_url: str,
    ) -> list[str]:
        html = self._fetch_html(root_url)

        if not html:
            return []

        usernames: list[str] = []
        seen: set[str] = set()

        self._collect_instagram_usernames(
            html=html,
            base_url=root_url,
            output=usernames,
            seen=seen,
        )

        if usernames:
            return usernames

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        internal_pages = self._find_internal_pages(
            soup=soup,
            root_url=root_url,
        )

        for page_url in internal_pages[: self._max_internal_pages_per_site]:
            if self._request_delay_seconds > 0:
                self._sleeper(self._request_delay_seconds)

            page_html = self._fetch_html(page_url)

            if not page_html:
                continue

            self._collect_instagram_usernames(
                html=page_html,
                base_url=page_url,
                output=usernames,
                seen=seen,
            )

        return usernames

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

        content_type = response.headers.get("content-type", "").lower()

        if "text/html" not in content_type and "application/xhtml" not in content_type:
            return ""

        return response.text

    def _collect_instagram_usernames(
        self,
        *,
        html: str,
        base_url: str,
        output: list[str],
        seen: set[str],
    ) -> None:
        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        # First: normal <a href="instagram...">
        for anchor in soup.find_all(
            "a",
            href=True,
        ):
            raw_href = str(anchor.get("href") or "").strip()

            href = urljoin(
                base_url,
                raw_href,
            )

            username = self._instagram_username_from_url(href)

            if username is None:
                continue

            if username in seen:
                continue

            seen.add(username)
            output.append(username)

        # Second: Instagram URLs embedded in HTML/JS.
        patterns = (
            r"https?://(?:www\.)?instagram\.com/" r"(?P<username>[a-zA-Z0-9._]{1,30})"
        )

        for match in re.finditer(
            patterns,
            html,
            flags=re.IGNORECASE,
        ):
            username = match.group("username").lower()

            if username in self._BLOCKED_INSTAGRAM_SEGMENTS:
                continue

            if self._INSTAGRAM_USERNAME_PATTERN.fullmatch(username) is None:
                continue

            if username in seen:
                continue

            seen.add(username)
            output.append(username)

    def _instagram_username_from_url(
        self,
        url: str,
    ) -> str | None:
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

        username = parts[0].strip().lstrip("@").lower()

        if username in self._BLOCKED_INSTAGRAM_SEGMENTS:
            return None

        if self._INSTAGRAM_USERNAME_PATTERN.fullmatch(username) is None:
            return None

        return username

    def _find_internal_pages(
        self,
        *,
        soup: BeautifulSoup,
        root_url: str,
    ) -> list[str]:
        root = urlparse(root_url)

        root_host = (root.hostname or "").lower()

        result: list[str] = []
        seen: set[str] = set()

        for anchor in soup.find_all(
            "a",
            href=True,
        ):
            href = str(anchor.get("href") or "")

            text = anchor.get_text(
                " ",
                strip=True,
            ).lower()

            absolute = urljoin(
                root_url,
                href,
            )

            parsed = urlparse(absolute)

            if (parsed.hostname or "").lower() != root_host:
                continue

            searchable = f"{parsed.path} {text}".lower()

            if not any(hint in searchable for hint in self._INTERNAL_PATH_HINTS):
                continue

            key = absolute.rstrip("/")

            if key in seen:
                continue

            seen.add(key)

            result.append(absolute)

        return result

    @staticmethod
    def _website_key(
        url: str,
    ) -> str:
        parsed = urlparse(url)

        hostname = (parsed.hostname or "").lower()

        return hostname.removeprefix("www.")
