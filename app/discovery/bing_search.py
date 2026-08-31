from __future__ import annotations

import re
import time
from collections.abc import Callable
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from app.discovery.base import DiscoverySource


class BingSearchDiscoverySource(DiscoverySource):
    """
    Secondary discovery source based on ordinary
    public Bing result pages.

    No API key is required.

    This source only extracts public Instagram profile URLs
    appearing in ordinary search results.
    """

    _SEARCH_URL = "https://www.bing.com/search"

    _USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9._]+$")

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

    def __init__(
        self,
        *,
        timeout_seconds: float = 15.0,
        request_delay_seconds: float = 1.5,
        max_pages_per_query: int = 5,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._timeout_seconds = timeout_seconds

        self._request_delay_seconds = request_delay_seconds

        self._max_pages_per_query = max_pages_per_query

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
                "Accept-Language": ("en-US,en;q=0.9"),
            }
        )

    def discover(
        self,
        *,
        query: str,
        limit: int,
    ) -> list[str]:
        query = query.strip()

        if not query or limit <= 0:
            return []

        usernames: list[str] = []
        seen: set[str] = set()

        for page_index in range(self._max_pages_per_query):
            if len(usernames) >= limit:
                break

            first = (page_index * 10) + 1

            html = self._fetch(
                query=query,
                first=first,
            )

            if not html:
                break

            candidates = self._extract_usernames(html)

            new_count = 0

            for username in candidates:
                if username in seen:
                    continue

                seen.add(username)
                usernames.append(username)

                new_count += 1

                if len(usernames) >= limit:
                    break

            if new_count == 0:
                break

            if page_index + 1 < self._max_pages_per_query:
                self._sleeper(self._request_delay_seconds)

        return usernames

    def _fetch(
        self,
        *,
        query: str,
        first: int,
    ) -> str:
        try:
            response = self._session.get(
                self._SEARCH_URL,
                params={
                    "q": query,
                    "first": first,
                    "count": 10,
                },
                timeout=self._timeout_seconds,
            )

        except requests.RequestException:
            return ""

        if response.status_code != 200:
            return ""

        return response.text

    def _extract_usernames(
        self,
        html: str,
    ) -> list[str]:
        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        usernames: list[str] = []
        seen: set[str] = set()

        selectors = (
            "li.b_algo h2 a",
            "li.b_algo a",
            "a[href]",
        )

        anchors = []

        for selector in selectors:
            found = soup.select(selector)

            if found:
                anchors.extend(found)

        for anchor in anchors:
            href = anchor.get("href")

            if not href:
                continue

            username = self._username_from_url(str(href))

            if username is None:
                continue

            if username in seen:
                continue

            seen.add(username)
            usernames.append(username)

        return usernames

    def _username_from_url(
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

        username = parts[0].strip().lower()

        if username in self._BLOCKED_INSTAGRAM_SEGMENTS:
            return None

        if self._USERNAME_PATTERN.fullmatch(username) is None:
            return None

        return username
