import json
import re
from collections.abc import Mapping
from typing import Any, Final

import httpx
from bs4 import BeautifulSoup
from pydantic import HttpUrl

from app.crawler.base import ProfileFetcher
from app.crawler.exceptions import (
    ProfileFetchError,
    ProfileNotFoundError,
    RateLimitError,
)
from app.models.external_link import (
    ExternalLink,
    ExternalLinkType,
)
from app.models.raw_profile import RawProfileData


class InstagramHttpProfileFetcher(ProfileFetcher):
    """HTTP client fetcher that scrapes and parses public Instagram profile web pages."""

    _BASE_URL: Final[str] = "https://www.instagram.com"

    _USER_AGENT: Final[str] = (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    )

    def __init__(
        self,
        *,
        timeout_seconds: float = 15.0,
    ) -> None:
        """Initializes the HTTP client with custom headers and timeout settings.

        Args:
            timeout_seconds: Timeout threshold for HTTP requests in seconds. Defaults to 15.0.
        """
        self._client = httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": self._USER_AGENT,
                "Accept": (
                    "text/html,"
                    "application/xhtml+xml,"
                    "application/xml;q=0.9,"
                    "*/*;q=0.8"
                ),
                "Accept-Language": ("en-US,en;q=0.9"),
            },
        )

    def fetch(self, username: str) -> RawProfileData:
        """Fetches public Instagram profile metadata for a given username.

        Args:
            username: Target Instagram handle (with or without leading '@').

        Returns:
            A RawProfileData model containing scraped metadata and external links.

        Raises:
            ValueError: If the username is empty after normalization.
            ProfileNotFoundError: If the requested profile returned HTTP 404.
            RateLimitError: If Instagram returned HTTP 429 Too Many Requests.
            ProfileFetchError: On network failures, access blocks, or bad status codes.
        """
        normalized_username = self._normalize_username(username)

        url = f"{self._BASE_URL}/" f"{normalized_username}/"

        try:
            response = self._client.get(url)

        except httpx.RequestError as exc:
            raise ProfileFetchError(
                f"Network error while fetching " f"'@{normalized_username}': " f"{exc}"
            ) from exc

        # Validate HTTP status before attempting HTML extraction
        self._raise_for_status(
            response=response,
            username=normalized_username,
        )

        return self._parse_profile(
            username=normalized_username,
            html=response.text,
        )

    @staticmethod
    def _raise_for_status(*, response: httpx.Response, username: str) -> None:
        """Validates response status codes and raises domain-specific exceptions.

        Args:
            response: The HTTP response from Instagram.
            username: Target username associated with the request.

        Raises:
            ProfileNotFoundError: On HTTP 404.
            RateLimitError: On HTTP 429.
            ProfileFetchError: On HTTP 401, 403, or general 4xx/5xx status codes.
        """
        if response.status_code == 404:
            raise ProfileNotFoundError(
                f"Instagram profile " f"'@{username}' was not found."
            )

        if response.status_code == 429:
            raise RateLimitError("Instagram returned HTTP 429 " "Too Many Requests.")

        if response.status_code in {
            401,
            403,
        }:
            raise ProfileFetchError(
                "Instagram blocked public access " f"with HTTP {response.status_code}."
            )

        if response.is_error:
            raise ProfileFetchError(
                f"Instagram returned " f"HTTP {response.status_code}."
            )

    def _parse_profile(self, *, username: str, html: str) -> RawProfileData:
        """Parses raw HTML payload to extract metadata from OpenGraph meta tags and JSON-LD scripts.

        Args:
            username: The target profile username.
            html: Raw HTML response body from Instagram.

        Returns:
            A populated RawProfileData instance.

        Raises:
            ProfileFetchError: If no usable profile metadata was found in the HTML.
        """
        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        description = self._read_meta_content(
            soup=soup,
            property_name="og:description",
        )

        title = self._read_meta_content(
            soup=soup,
            property_name="og:title",
        )

        structured_data = self._extract_json_ld(soup)

        followers_count = 0
        following_count = 0
        posts_count = 0
        bio: str | None = None
        display_name: str | None = None
        external_links: tuple[ExternalLink, ...] = ()

        # Extract counts and bio snippet from og:description meta tag
        if description:
            (
                followers_count,
                following_count,
                posts_count,
            ) = self._parse_counts_from_description(description)

            bio = self._parse_bio_from_description(description)

        # Extract display name from og:title meta tag
        if title:
            display_name = self._parse_display_name(title)

        # Fallback to structured JSON-LD data for missing fields
        if structured_data:
            json_ld_name = structured_data.get("name")

            if not display_name and isinstance(
                json_ld_name,
                str,
            ):
                display_name = json_ld_name.strip() or None

            json_ld_description = structured_data.get("description")

            if not bio and isinstance(
                json_ld_description,
                str,
            ):
                bio = json_ld_description.strip() or None

            external_links = self._extract_links_from_json_ld(structured_data)

        # Raise an error if all extraction channels failed
        if not title and not description and not structured_data:
            raise ProfileFetchError(
                "Instagram returned HTML, "
                "but expected public profile "
                "metadata was not found."
            )

        return RawProfileData(
            username=username,
            display_name=display_name,
            bio=bio,
            external_links=external_links,
            followers_count=followers_count,
            following_count=following_count,
            posts_count=posts_count,
            is_public=True,
        )

    @staticmethod
    def _read_meta_content(*, soup: BeautifulSoup, property_name: str) -> str | None:
        """Extracts the string content of a specific HTML meta tag.

        Args:
            soup: Parsed BeautifulSoup object.
            property_name: Target OpenGraph property attribute (e.g., 'og:title').

        Returns:
            The trimmed content attribute string, or None if tag/attribute is missing or empty.
        """
        tag = soup.find(
            "meta",
            attrs={
                "property": property_name,
            },
        )

        if tag is None:
            return None

        content = tag.get("content")

        if not isinstance(
            content,
            str,
        ):
            return None

        stripped = content.strip()

        return stripped or None

    @staticmethod
    def _extract_json_ld(soup: BeautifulSoup) -> Mapping[str, Any] | None:
        """Locates and parses the embedded application/ld+json script block in the HTML.

        Args:
            soup: Parsed BeautifulSoup object.

        Returns:
            A dictionary containing parsed JSON-LD data, or None if missing or invalid.
        """
        scripts = soup.find_all(
            "script",
            attrs={"type": ("application/ld+json")},
        )

        for script in scripts:
            raw = script.string

            if not raw:
                continue

            try:
                parsed = json.loads(raw)

            except json.JSONDecodeError:
                continue

            if isinstance(
                parsed,
                Mapping,
            ):
                return parsed

        return None

    @staticmethod
    def _parse_display_name(title: str) -> str | None:
        """Strips Instagram page title suffixes from the profile title string.

        Args:
            title: Raw title string (e.g., "John Doe (@johndoe) • Instagram photos and videos").

        Returns:
            Cleaned display name or None if empty.
        """
        cleaned = re.sub(
            r"\s*\(@[^)]+\)\s*•\s*Instagram.*$",
            "",
            title,
            flags=re.IGNORECASE,
        ).strip()

        if not cleaned:
            return None

        return cleaned

    def _parse_counts_from_description(self, description: str) -> tuple[int, int, int]:
        """Parses follower, following, and post counts from an OpenGraph description string.

        Args:
            description: OpenGraph description content text.

        Returns:
            A tuple of (followers_count, following_count, posts_count).
        """
        followers = self._extract_count(
            description,
            "followers",
        )

        following = self._extract_count(
            description,
            "following",
        )

        posts = self._extract_count(
            description,
            "posts",
        )

        return (
            followers,
            following,
            posts,
        )

    def _extract_count(self, text: str, label: str) -> int:
        """Extracts a numeric quantity preceding a specific metric label using regex.

        Args:
            text: The text string to search within.
            label: Metric label (e.g., "followers", "following", "posts").

        Returns:
            Parsed whole integer value, or 0 if no match was found.
        """
        pattern = rf"([\d.,]+[KMB]?)" rf"\s+{re.escape(label)}"

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match is None:
            return 0

        return self._parse_compact_count(match.group(1))

    @staticmethod
    def _parse_compact_count(value: str) -> int:
        """Converts compact numerical strings with K/M/B suffixes to integers.

        Args:
            value: Compact number string (e.g., "1.5M", "468K", "1,200").

        Returns:
            The integer count value.
        """
        normalized = value.strip().lower().replace(",", "")

        multipliers = {
            "k": 1_000,
            "m": 1_000_000,
            "b": 1_000_000_000,
        }

        suffix = normalized[-1]

        if suffix in multipliers:
            number = float(normalized[:-1])

            return int(number * multipliers[suffix])

        return int(float(normalized))

    @staticmethod
    def _parse_bio_from_description(description: str) -> str | None:
        """Extracts the profile bio section appended after the dash in og:description.

        Args:
            description: OpenGraph description string.

        Returns:
            Extracted bio string, or None if separator is not found or bio is empty.
        """
        separator = " - "

        if separator not in description:
            return None

        _, bio = description.split(
            separator,
            maxsplit=1,
        )

        cleaned = bio.strip()

        return cleaned or None

    def _extract_links_from_json_ld(
        self,
        data: Mapping[str, Any],
    ) -> tuple[ExternalLink, ...]:
        """Extracts and parses external URLs from the JSON-LD 'sameAs' property array.

        Args:
            data: Parsed JSON-LD mapping dictionary.

        Returns:
            A tuple of deduplicated ExternalLink models.
        """
        raw_same_as = data.get("sameAs")

        if not isinstance(
            raw_same_as,
            list,
        ):
            return ()

        links: list[ExternalLink] = []

        seen: set[str] = set()

        for value in raw_same_as:
            if not isinstance(
                value,
                str,
            ):
                continue

            url = value.strip()

            if not url or url in seen:
                continue

            links.append(
                ExternalLink(
                    # Wrap with HttpUrl for static type compatibility with Pydantic v2
                    url=HttpUrl(url),
                    title=None,
                    type=self._detect_link_type(url),
                )
            )

            seen.add(url)

        return tuple(links)

    @staticmethod
    def _detect_link_type(url: str) -> ExternalLinkType:
        """Detects the category type of an external URL based on domain signatures.

        Args:
            url: Target URL string to evaluate.

        Returns:
            The matched ExternalLinkType enum variant.
        """
        normalized = url.lower()

        if "wa.me/" in normalized or "whatsapp.com/" in normalized:
            return ExternalLinkType.WHATSAPP

        if "t.me/" in normalized or "telegram.me/" in normalized:
            return ExternalLinkType.TELEGRAM

        if any(
            domain in normalized
            for domain in (
                "takl.ink/",
                "linktr.ee/",
                "zil.ink/",
                "bio.link/",
            )
        ):
            return ExternalLinkType.LINK_IN_BIO

        return ExternalLinkType.WEBSITE
