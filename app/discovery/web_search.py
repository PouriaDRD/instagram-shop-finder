import re
import time
from collections.abc import Callable
from html.parser import HTMLParser
from urllib.parse import (
    parse_qs,
    quote_plus,
    unquote,
    urlparse,
)
from urllib.request import (
    Request,
    urlopen,
)

from app.discovery.base import DiscoverySource


class _SearchResultLinkParser(HTMLParser):
    """
    Minimal HTML parser for collecting search-result links.

    We intentionally avoid depending on BeautifulSoup or another
    third-party HTML parsing package.
    """

    def __init__(self) -> None:
        super().__init__()

        self.links: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.lower() != "a":
            return

        attributes = dict(attrs)

        href = attributes.get("href")

        if not href:
            return

        self.links.append(href)


class WebSearchDiscoverySource(DiscoverySource):
    """
    Discover candidate public Instagram usernames through ordinary
    public web-search results.

    This class does NOT:
    - log in to Instagram
    - bypass CAPTCHA
    - bypass search-engine restrictions
    - use stealth browser techniques
    - bypass rate limits

    If the search source stops returning accessible public results,
    the caller simply receives fewer or zero candidates.
    """

    _SEARCH_URL = "https://html.duckduckgo.com/html/"

    _BLOCKED_INSTAGRAM_SEGMENTS = {
        "about",
        "accounts",
        "api",
        "developer",
        "developers",
        "direct",
        "directory",
        "explore",
        "legal",
        "oauth",
        "p",
        "privacy",
        "reel",
        "reels",
        "stories",
        "web",
    }

    _USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9._]+$")

    _INSTAGRAM_TEXT_PATTERN = re.compile(
        r"(?:https?://)?"
        r"(?:www\.)?"
        r"instagram\.com/"
        r"(?P<username>[a-zA-Z0-9._]+)"
        r"(?:/|$)",
        flags=re.IGNORECASE,
    )

    def __init__(
        self,
        *,
        timeout_seconds: float = 15.0,
        request_delay_seconds: float = 1.0,
        sleeper: Callable[
            [float],
            None,
        ] = time.sleep,
    ) -> None:
        self._timeout_seconds = timeout_seconds

        self._request_delay_seconds = request_delay_seconds

        self._sleeper = sleeper

    def discover(self, *, query: str, limit: int) -> list[str]:
        if limit <= 0:
            return []

        normalized_query = query.strip()

        if not normalized_query:
            return []

        usernames: list[str] = []

        seen: set[str] = set()

        # A few ordinary result pages are enough for the
        # first discovery implementation.
        #
        # We intentionally keep this bounded.
        page_offsets = (
            0,
            30,
            60,
            90,
        )

        for page_index, offset in enumerate(page_offsets):
            if len(usernames) >= limit:
                break

            if page_index > 0:
                self._sleeper(self._request_delay_seconds)

            html = self._fetch_search_page(
                query=normalized_query,
                offset=offset,
            )

            if not html:
                break

            candidates = self._extract_usernames(html)

            new_count = 0

            for username in candidates:
                key = username.lower()

                if key in seen:
                    continue

                seen.add(key)

                usernames.append(username)

                new_count += 1

                if len(usernames) >= limit:
                    break

            # If a result page produced nothing new,
            # continuing to request more pages usually
            # provides little value.
            if new_count == 0:
                break

        return usernames

    def _fetch_search_page(self, *, query: str, offset: int) -> str:
        encoded_query = quote_plus(query)

        url = f"{self._SEARCH_URL}" f"?q={encoded_query}" f"&s={offset}"

        request = Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/131.0 Safari/537.36"
                ),
                "Accept": ("text/html," "application/xhtml+xml"),
                "Accept-Language": ("en-US,en;q=0.9"),
            },
            method="GET",
        )

        try:
            with urlopen(
                request,
                timeout=self._timeout_seconds,
            ) as response:
                status = getattr(
                    response,
                    "status",
                    200,
                )

                if status != 200:
                    return ""

                raw = response.read()

        except Exception:
            return ""

        try:
            return raw.decode(
                "utf-8",
                errors="replace",
            )

        except Exception:
            return ""

    def _extract_usernames(self, html: str) -> list[str]:
        usernames: list[str] = []

        seen: set[str] = set()

        parser = _SearchResultLinkParser()

        try:
            parser.feed(html)

        except Exception:
            pass

        for raw_url in parser.links:
            target = self._unwrap_search_redirect(raw_url)

            username = self._username_from_instagram_url(target)

            if username is None:
                continue

            key = username.lower()

            if key in seen:
                continue

            seen.add(key)

            usernames.append(username)

        # Search-result snippets sometimes contain a
        # visible Instagram URL even when the anchor itself
        # points through another search-engine route.
        for match in self._INSTAGRAM_TEXT_PATTERN.finditer(html):
            username = match.group("username")

            username = username.strip().lower()

            if not self._is_valid_username(username):
                continue

            if username in seen:
                continue

            seen.add(username)

            usernames.append(username)

        return usernames

    @staticmethod
    def _unwrap_search_redirect(url: str) -> str:
        raw = url.strip()

        if raw.startswith("//"):
            raw = "https:" + raw

        parsed = urlparse(raw)

        hostname = (parsed.hostname or "").lower()

        if hostname not in {
            "duckduckgo.com",
            "www.duckduckgo.com",
        }:
            return raw

        query = parse_qs(parsed.query)

        targets = query.get("uddg")

        if not targets:
            return raw

        return unquote(targets[0])

    def _username_from_instagram_url(self, url: str) -> str | None:
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

        if not self._is_valid_username(username):
            return None

        return username

    def _is_valid_username(self, username: str) -> bool:
        if not username:
            return False

        if username in self._BLOCKED_INSTAGRAM_SEGMENTS:
            return False

        return self._USERNAME_PATTERN.fullmatch(username) is not None
