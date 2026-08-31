from __future__ import annotations

import re
import time
from collections.abc import Callable
from urllib.parse import parse_qs, unquote, urlparse

import requests
from bs4 import BeautifulSoup

from app.discovery.base import DiscoverySource


class WebSearchDiscoverySource(DiscoverySource):
    """
    Public web-search discovery using DuckDuckGo Lite.

    BeautifulSoup is used only for parsing public HTML.

    No login, CAPTCHA bypass, proxy rotation, stealth,
    or rate-limit circumvention is performed.
    """

    _SEARCH_URL = "https://lite.duckduckgo.com/lite/"

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
                "Accept": (
                    "text/html,"
                    "application/xhtml+xml,"
                    "application/xml;q=0.9,"
                    "*/*;q=0.8"
                ),
                "Accept-Language": "en-US,en;q=0.9",
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

        query = query.strip()

        if not query:
            return []

        usernames: list[str] = []
        seen: set[str] = set()

        page_data: dict[str, str] = {
            "q": query,
        }

        for page_index in range(self._max_pages_per_query):
            if len(usernames) >= limit:
                break

            html = self._request_page(data=page_data)

            if not html:
                break

            soup = BeautifulSoup(
                html,
                "html.parser",
            )

            found_on_page = self._extract_usernames(
                soup=soup,
                html=html,
            )

            new_count = 0

            for username in found_on_page:
                key = username.lower()

                if key in seen:
                    continue

                seen.add(key)
                usernames.append(username)
                new_count += 1

                if len(usernames) >= limit:
                    break

            next_data = self._extract_next_page_data(soup)

            if not next_data:
                break

            if page_index > 0 and new_count == 0:
                break

            page_data = next_data

            self._sleeper(self._request_delay_seconds)

        return usernames

    def _request_page(
        self,
        *,
        data: dict[str, str],
    ) -> str:
        try:
            response = self._session.post(
                self._SEARCH_URL,
                data=data,
                timeout=self._timeout_seconds,
            )

        except requests.RequestException:
            return ""

        if response.status_code != 200:
            return ""

        if not response.text:
            return ""

        return response.text

    def _extract_usernames(
        self,
        *,
        soup: BeautifulSoup,
        html: str,
    ) -> list[str]:
        usernames: list[str] = []
        seen: set[str] = set()

        for anchor in soup.find_all(
            "a",
            href=True,
        ):
            href = str(anchor.get("href") or "")

            target = self._unwrap_search_redirect(href)

            username = self._username_from_instagram_url(target)

            if username is None:
                continue

            if username in seen:
                continue

            seen.add(username)
            usernames.append(username)

        for match in self._INSTAGRAM_TEXT_PATTERN.finditer(html):
            username = match.group("username").strip().lower()

            if not self._is_valid_username(username):
                continue

            if username in seen:
                continue

            seen.add(username)
            usernames.append(username)

        return usernames

    @staticmethod
    def _extract_next_page_data(
        soup: BeautifulSoup,
    ) -> dict[str, str] | None:
        forms = soup.find_all("form")

        for form in forms:
            inputs = form.find_all("input")

            values: dict[str, str] = {}

            has_next_signal = False

            for input_element in inputs:
                name = input_element.get("name")

                value = input_element.get("value")

                input_type = (str(input_element.get("type") or "")).lower()

                if not name:
                    continue

                if value is None:
                    value = ""

                values[str(name)] = str(value)

                if input_type == "submit" and "next" in str(value).lower():
                    has_next_signal = True

            if has_next_signal and "q" in values:
                return values

        return None

    @staticmethod
    def _unwrap_search_redirect(
        url: str,
    ) -> str:
        raw = url.strip()

        if raw.startswith("//"):
            raw = "https:" + raw

        parsed = urlparse(raw)

        hostname = (parsed.hostname or "").lower()

        if hostname not in {
            "duckduckgo.com",
            "www.duckduckgo.com",
            "lite.duckduckgo.com",
        }:
            return raw

        query = parse_qs(parsed.query)

        targets = query.get("uddg")

        if not targets:
            return raw

        return unquote(targets[0])

    def _username_from_instagram_url(
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
