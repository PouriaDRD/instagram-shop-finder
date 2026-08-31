from __future__ import annotations

import re
import time
from collections.abc import Callable
from urllib.parse import (
    parse_qs,
    unquote,
    urljoin,
    urlparse,
)

import requests
from bs4 import BeautifulSoup

from app.discovery.base import DiscoverySource


class GoogleDeepDiscoverySource(DiscoverySource):
    """
    Deep public-web discovery using normal Google Search pages.

    Discovery paths:

    1. Google result -> direct Instagram profile
    2. Google result -> shop website -> Instagram social link
    3. Shop website -> contact/about/social page -> Instagram link

    This source:
    - does not log in to Google or Instagram
    - does not bypass CAPTCHA/challenges
    - stops Google requests when a challenge/rate limit is detected
    """

    _GOOGLE_SEARCH_URL = "https://www.google.com/search"

    _USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._]{1,30}$")

    _INSTAGRAM_URL_PATTERN = re.compile(
        r"https?://(?:www\.)?instagram\.com/" r"(?P<username>[A-Za-z0-9._]{1,30})",
        flags=re.IGNORECASE,
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

    _BLOCKED_WEBSITE_HOSTS = {
        # Search/social platforms
        "google.com",
        "www.google.com",
        "bing.com",
        "www.bing.com",
        "instagram.com",
        "www.instagram.com",
        "facebook.com",
        "www.facebook.com",
        "youtube.com",
        "www.youtube.com",
        "tiktok.com",
        "www.tiktok.com",
        "x.com",
        "twitter.com",
        # Broad marketplaces/directories
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

    _INTERNAL_PAGE_HINTS = (
        "contact",
        "contact-us",
        "about",
        "about-us",
        "social",
        "instagram",
        "تماس",
        "درباره",
        "شبکه",
    )

    _CHALLENGE_MARKERS = (
        "our systems have detected unusual traffic",
        "unusual traffic from your computer network",
        "detected unusual traffic",
        "sorry/index",
        "recaptcha",
    )

    def __init__(
        self,
        *,
        search_pages_per_query: int = 4,
        results_per_page: int = 10,
        max_websites_per_query: int = 25,
        max_internal_pages_per_site: int = 3,
        timeout_seconds: float = 12.0,
        request_delay_seconds: float = 1.5,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._search_pages_per_query = search_pages_per_query

        self._results_per_page = results_per_page

        self._max_websites_per_query = max_websites_per_query

        self._max_internal_pages_per_site = max_internal_pages_per_site

        self._timeout_seconds = timeout_seconds

        self._request_delay_seconds = request_delay_seconds

        self._sleeper = sleeper

        self._google_stopped = False

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

        self._google_stopped = False

        queries = self._build_query_pack(query)

        usernames: list[str] = []

        seen_usernames: set[str] = set()
        seen_websites: set[str] = set()

        for google_query in queries:
            if len(usernames) >= limit:
                break

            if self._google_stopped:
                break

            result_urls = self._search_google(
                query=google_query,
            )

            websites_processed = 0

            for result_url in result_urls:
                if len(usernames) >= limit:
                    break

                direct_username = self._instagram_username_from_url(result_url)

                if direct_username is not None:
                    self._add_username(
                        direct_username,
                        output=usernames,
                        seen=seen_usernames,
                    )

                    continue

                if not self._is_candidate_website(result_url):
                    continue

                website_key = self._website_key(result_url)

                if not website_key or website_key in seen_websites:
                    continue

                if websites_processed >= self._max_websites_per_query:
                    break

                seen_websites.add(website_key)

                websites_processed += 1

                website_usernames = self._discover_from_website(result_url)

                for username in website_usernames:
                    self._add_username(
                        username,
                        output=usernames,
                        seen=seen_usernames,
                    )

                    if len(usernames) >= limit:
                        break

                self._sleep()

        return usernames

    def _build_query_pack(
        self,
        original_query: str,
    ) -> list[str]:
        phrase = self._clean_query(original_query)

        if not phrase:
            phrase = "فروشگاه آنلاین"

        negative_sites = (
            "-site:digikala.com "
            "-site:torob.com "
            "-site:basalam.com "
            "-site:emalls.ir "
            "-site:technolife.ir"
        )

        candidates = [
            # Direct Instagram index discovery
            f'site:instagram.com "{phrase}"',
            f'site:instagram.com "{phrase}" فروشگاه',
            f'site:instagram.com "{phrase}" خرید',
            f'site:instagram.com "{phrase}" سفارش',
            f'site:instagram.com "{phrase}" دایرکت',
            # Find websites mentioning Instagram
            (f'"{phrase}" "instagram.com" ' f"{negative_sites}"),
            (f'"{phrase}" "اینستاگرام" ' f"{negative_sites}"),
            (f'"{phrase}" "پیج اینستاگرام" ' f"{negative_sites}"),
            # Find actual shop websites
            (f'"{phrase}" "فروشگاه اینترنتی" ' f"{negative_sites}"),
            (f'"{phrase}" "خرید آنلاین" ' f"{negative_sites}"),
            (f'"{phrase}" "ثبت سفارش" ' f"{negative_sites}"),
            (f'"{phrase}" "تماس با ما" ' f"instagram {negative_sites}"),
            # Less strict query for recall
            (f"{phrase} فروشگاه اینستاگرام " f"{negative_sites}"),
            (f"{phrase} فروشگاه آنلاین " f"{negative_sites}"),
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

    @staticmethod
    def _clean_query(
        query: str,
    ) -> str:
        cleaned = re.sub(
            r"\bsite\s*:\s*instagram\.com\b",
            "",
            query,
            flags=re.IGNORECASE,
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

    def _search_google(
        self,
        *,
        query: str,
    ) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()

        for page_index in range(self._search_pages_per_query):
            if self._google_stopped:
                break

            start = page_index * self._results_per_page

            html = self._fetch_google_page(
                query=query,
                start=start,
            )

            if not html:
                break

            page_urls = self._extract_google_result_urls(html)

            new_count = 0

            for url in page_urls:
                key = self._url_key(url)

                if not key:
                    continue

                if key in seen:
                    continue

                seen.add(key)

                urls.append(url)

                new_count += 1

            if new_count == 0:
                break

            self._sleep()

        return urls

    def _fetch_google_page(
        self,
        *,
        query: str,
        start: int,
    ) -> str:
        try:
            response = self._session.get(
                self._GOOGLE_SEARCH_URL,
                params={
                    "q": query,
                    "start": start,
                    "num": self._results_per_page,
                    "hl": "fa",
                    "filter": "0",
                },
                timeout=self._timeout_seconds,
                allow_redirects=True,
            )

        except requests.RequestException:
            return ""

        if response.status_code in {
            403,
            429,
        }:
            self._google_stopped = True
            return ""

        if response.status_code != 200:
            return ""

        final_url = response.url.lower()

        body_lower = response.text.lower()

        if "/sorry/" in final_url or any(
            marker in body_lower for marker in self._CHALLENGE_MARKERS
        ):
            self._google_stopped = True
            return ""

        return response.text

    def _extract_google_result_urls(
        self,
        html: str,
    ) -> list[str]:
        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        urls: list[str] = []
        seen: set[str] = set()

        for anchor in soup.find_all(
            "a",
            href=True,
        ):
            raw_href = str(anchor.get("href") or "").strip()

            destination = self._decode_google_url(raw_href)

            if destination is None:
                continue

            if not destination.startswith(
                (
                    "http://",
                    "https://",
                )
            ):
                continue

            if self._is_google_internal_url(destination):
                continue

            key = self._url_key(destination)

            if not key or key in seen:
                continue

            seen.add(key)

            urls.append(destination)

        return urls

    @staticmethod
    def _decode_google_url(
        href: str,
    ) -> str | None:
        if not href:
            return None

        if href.startswith(
            (
                "http://",
                "https://",
            )
        ):
            parsed = urlparse(href)

            hostname = (parsed.hostname or "").lower()

            if hostname.endswith("google.com") and parsed.path == "/url":
                query = parse_qs(parsed.query)

                values = query.get("q") or query.get("url")

                if not values:
                    return None

                return unquote(values[0])

            return href

        if href.startswith("/url?"):
            parsed = urlparse(href)

            query = parse_qs(parsed.query)

            values = query.get("q") or query.get("url")

            if not values:
                return None

            return unquote(values[0])

        return None

    @staticmethod
    def _is_google_internal_url(
        url: str,
    ) -> bool:
        parsed = urlparse(url)

        hostname = (parsed.hostname or "").lower()

        if not hostname:
            return True

        return hostname == "google.com" or hostname.endswith(".google.com")

    def _discover_from_website(
        self,
        url: str,
    ) -> list[str]:
        root_url = self._root_url(url)

        if root_url is None:
            return []

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

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        internal_pages = self._find_internal_pages(
            soup=soup,
            root_url=root_url,
        )

        for internal_url in internal_pages[: self._max_internal_pages_per_site]:
            self._sleep()

            internal_html = self._fetch_html(internal_url)

            if not internal_html:
                continue

            self._collect_instagram_usernames(
                html=internal_html,
                base_url=internal_url,
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

        # Normal anchor links
        for anchor in soup.find_all(
            "a",
            href=True,
        ):
            raw_href = str(anchor.get("href") or "").strip()

            absolute_url = urljoin(
                base_url,
                raw_href,
            )

            username = self._instagram_username_from_url(absolute_url)

            if username is None:
                continue

            if username in seen:
                continue

            seen.add(username)

            output.append(username)

        # Instagram URLs embedded in HTML / JS
        for match in self._INSTAGRAM_URL_PATTERN.finditer(html):
            username = match.group("username").lower()

            if not self._is_valid_username(username):
                continue

            if username in seen:
                continue

            seen.add(username)

            output.append(username)

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

            hostname = (parsed.hostname or "").lower()

            if hostname != root_host:
                continue

            searchable = f"{parsed.path} {text}".casefold()

            if not any(hint in searchable for hint in self._INTERNAL_PAGE_HINTS):
                continue

            key = absolute.rstrip("/")

            if key in seen:
                continue

            seen.add(key)

            result.append(absolute)

        return result

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

        if not self._is_valid_username(username):
            return None

        return username

    def _is_valid_username(
        self,
        username: str,
    ) -> bool:
        if not username:
            return False

        if username in self._BLOCKED_INSTAGRAM_SEGMENTS:
            return False

        return self._USERNAME_PATTERN.fullmatch(username) is not None

    def _is_candidate_website(
        self,
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

        normalized = hostname.removeprefix("www.")

        for blocked in self._BLOCKED_WEBSITE_HOSTS:
            if normalized == blocked.removeprefix("www."):
                return False

        return True

    @staticmethod
    def _root_url(
        url: str,
    ) -> str | None:
        parsed = urlparse(url)

        if (
            parsed.scheme
            not in {
                "http",
                "https",
            }
            or not parsed.netloc
        ):
            return None

        return f"{parsed.scheme}://" f"{parsed.netloc}/"

    @staticmethod
    def _website_key(
        url: str,
    ) -> str:
        parsed = urlparse(url)

        return (parsed.hostname or "").lower().removeprefix("www.")

    @staticmethod
    def _url_key(
        url: str,
    ) -> str:
        parsed = urlparse(url)

        hostname = (parsed.hostname or "").lower()

        if not hostname:
            return ""

        hostname = hostname.removeprefix("www.")

        return (
            f"{hostname}" f"{parsed.path.rstrip('/')}" f"?{parsed.query}"
            if parsed.query
            else (f"{hostname}" f"{parsed.path.rstrip('/')}")
        )

    def _add_username(
        self,
        username: str,
        *,
        output: list[str],
        seen: set[str],
    ) -> None:
        normalized = username.strip().lstrip("@").lower()

        if not self._is_valid_username(normalized):
            return

        if normalized in seen:
            return

        seen.add(normalized)

        output.append(normalized)

    def _sleep(
        self,
    ) -> None:
        if self._request_delay_seconds > 0:
            self._sleeper(self._request_delay_seconds)
