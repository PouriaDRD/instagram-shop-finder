import re
import unicodedata
from typing import Final
from urllib.parse import parse_qs, unquote, urlparse

from pydantic import HttpUrl
from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

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


class InstagramPlaywrightProfileFetcher(ProfileFetcher):
    """Playwright-based fetcher that launches a headless Chromium browser instance to scrape public Instagram profile metadata."""

    _BASE_URL: Final[str] = "https://www.instagram.com"

    _NAVIGATION_TIMEOUT_MS: Final[int] = 30_000
    _RENDER_TIMEOUT_MS: Final[int] = 15_000
    _BODY_TIMEOUT_MS: Final[int] = 8_000

    # Header control lines to ignore when extracting bio text
    _IGNORED_HEADER_LINES: Final[frozenset[str]] = frozenset(
        {
            "follow",
            "following",
            "message",
            "contact",
            "email",
            "more",
            "see translation",
            "follow back",
        }
    )

    def fetch(
        self,
        username: str,
    ) -> RawProfileData:
        """Launches a browser session to fetch public Instagram profile data.

        Args:
            username: Target Instagram handle (with or without leading '@').

        Returns:
            A RawProfileData instance containing extracted profile metadata.

        Raises:
            ValueError: If the normalized username is empty.
            ProfileNotFoundError: If Instagram returns a 404 status.
            RateLimitError: If Instagram limits requests with HTTP 429.
            ProfileFetchError: On timeouts, access blocks, login walls, or unexpected browser errors.
        """
        normalized_username = self._normalize_username(username)

        url = f"{self._BASE_URL}/{normalized_username}/"

        try:
            with sync_playwright() as playwright:
                return self._fetch_with_browser(
                    playwright=playwright,
                    username=normalized_username,
                    url=url,
                )

        except ProfileFetchError:
            raise

        except Exception as exc:
            raise ProfileFetchError(
                "Unexpected browser error while "
                f"fetching '@{normalized_username}': "
                f"{exc}"
            ) from exc

    def _fetch_with_browser(
        self,
        *,
        playwright: Playwright,
        username: str,
        url: str,
    ) -> RawProfileData:
        """Manages the lifecycle of browser, context, and page objects during scraping.

        Args:
            playwright: Active Playwright sync runner context.
            username: Normalized target profile handle.
            url: Fully qualified Instagram profile URL.

        Returns:
            Extracted RawProfileData model.
        """
        browser = self._launch_browser(playwright)

        try:
            context = self._create_context(browser)

            try:
                page = context.new_page()

                return self._fetch_page(
                    page=page,
                    username=username,
                    url=url,
                )

            finally:
                context.close()

        finally:
            browser.close()

    @staticmethod
    def _launch_browser(
        playwright: Playwright,
    ) -> Browser:
        """Launches a headless Chromium browser instance."""
        return playwright.chromium.launch(
            headless=True,
        )

    @staticmethod
    def _create_context(
        browser: Browser,
    ) -> BrowserContext:
        """Configures an isolated browser context with a fixed viewport and English locale."""
        return browser.new_context(
            locale="en-US",
            viewport={
                "width": 1440,
                "height": 1000,
            },
        )

    def _fetch_page(
        self,
        *,
        page: Page,
        username: str,
        url: str,
    ) -> RawProfileData:
        """Navigates to the profile URL, validates HTTP status, checks for blocks, and parses metadata."""
        response = self._navigate(
            page=page,
            url=url,
            username=username,
        )

        if response is not None:
            status = response.status

            self._raise_for_status(
                status=status,
                username=username,
            )

        self._wait_for_profile_render(page)

        body_text = self._read_body_text(page)

        self._detect_blocked_page(body_text)

        title = self._read_meta(
            page=page,
            property_name="og:title",
        )

        description = self._read_meta(
            page=page,
            property_name="og:description",
        )

        if not title:
            document_title = page.title().strip()

            title = document_title or None

        header_text = self._read_profile_header_text(page)

        if not title and not description and not header_text:
            raise ProfileFetchError(
                "Instagram rendered the page, " "but profile data was not found."
            )

        display_name = self._parse_display_name(title) if title else None

        followers_count = self._extract_count(
            text=(description or header_text or body_text),
            label="followers",
        )

        following_count = self._extract_count(
            text=(description or header_text or body_text),
            label="following",
        )

        posts_count = self._extract_count(
            text=(description or header_text or body_text),
            label="posts",
        )

        external_links = self._extract_external_links(page)

        bio = self._extract_bio(
            username=username,
            display_name=display_name,
            header_text=header_text,
            description=description,
            external_links=external_links,
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

    def _navigate(
        self,
        *,
        page: Page,
        url: str,
        username: str,
    ):
        """Navigates to the target URL, listening for initial document commit.

        Instagram can keep background requests open for a long time. We only require
        the initial document and then separately wait for the profile header.
        """
        try:
            return page.goto(
                url,
                wait_until="commit",
                timeout=self._NAVIGATION_TIMEOUT_MS,
            )

        except PlaywrightTimeoutError:
            # Check if document loaded despite navigation timeout
            if page.url.startswith(self._BASE_URL):
                return None

            raise ProfileFetchError(f"Instagram page timed out for '@{username}'.")

    @staticmethod
    def _raise_for_status(
        *,
        status: int,
        username: str,
    ) -> None:
        """Validates response status code and raises domain exceptions."""
        if status == 404:
            raise ProfileNotFoundError(
                f"Instagram profile '@{username}' was not found."
            )

        if status == 429:
            raise RateLimitError("Instagram returned HTTP 429 Too Many Requests.")

        if status in {401, 403}:
            raise ProfileFetchError(
                f"Instagram blocked the request with HTTP {status}."
            )

        if status >= 400:
            raise ProfileFetchError(f"Instagram returned HTTP {status}.")

    def _wait_for_profile_render(
        self,
        page: Page,
    ) -> None:
        """Waits for profile header DOM elements to render, falling back to OpenGraph tags."""
        try:
            page.wait_for_selector(
                "header",
                state="attached",
                timeout=self._RENDER_TIMEOUT_MS,
            )

            return

        except PlaywrightTimeoutError:
            pass

        try:
            page.wait_for_selector(
                ('meta[property="og:title"], ' 'meta[property="og:description"]'),
                timeout=5_000,
            )

        except PlaywrightTimeoutError:
            pass

    def _read_body_text(
        self,
        page: Page,
    ) -> str:
        """Extracts visible inner text of the document body."""
        try:
            return page.locator("body").inner_text(timeout=self._BODY_TIMEOUT_MS)

        except PlaywrightTimeoutError:
            return ""

    @staticmethod
    def _read_profile_header_text(
        page: Page,
    ) -> str:
        """Extracts inner text from the main profile header element."""
        header = page.locator("header").first

        if header.count() == 0:
            return ""

        try:
            return header.inner_text(timeout=5_000).strip()

        except PlaywrightTimeoutError:
            return ""

    @staticmethod
    def _detect_blocked_page(
        body_text: str,
    ) -> None:
        """Scans page body text for challenge or restriction markers."""
        normalized = body_text.lower()

        blocked_markers = (
            "confirm it's you",
            "challenge required",
            "please wait a few minutes",
            "we restrict certain activity",
        )

        if any(marker in normalized for marker in blocked_markers):
            raise ProfileFetchError(
                "Instagram returned a challenge " "or restricted-access page."
            )

    @staticmethod
    def _read_meta(
        *,
        page: Page,
        property_name: str,
    ) -> str | None:
        """Reads the value of a specific HTML meta tag content attribute."""
        locator = page.locator(f'meta[property="{property_name}"]')

        if locator.count() == 0:
            return None

        content = locator.first.get_attribute("content")

        if not content:
            return None

        stripped = content.strip()

        return stripped or None

    @classmethod
    def _parse_display_name(
        cls,
        title: str,
    ) -> str | None:
        """Strips standard Instagram branding suffixes and cleans invisible Unicode characters from page title."""
        cleaned = re.sub(
            (r"\s*\(@[^)]+\)" r"\s*[•\-]\s*Instagram.*$"),
            "",
            title,
            flags=re.IGNORECASE,
        ).strip()

        cleaned = cls._clean_unicode_text(cleaned)

        return cleaned or None

    def _extract_bio(
        self,
        *,
        username: str,
        display_name: str | None,
        header_text: str,
        description: str | None,
        external_links: tuple[ExternalLink, ...],
    ) -> str | None:
        """Extracts bio text prioritising visible header lines over meta description fallbacks."""
        bio_from_header = self._extract_bio_from_header(
            username=username,
            display_name=display_name,
            header_text=header_text,
            external_links=external_links,
        )

        if bio_from_header:
            return bio_from_header

        return self._extract_bio_from_meta(description)

    def _extract_bio_from_header(
        self,
        *,
        username: str,
        display_name: str | None,
        header_text: str,
        external_links: tuple[ExternalLink, ...],
    ) -> str | None:
        """Parses bio lines out of raw header text by stripping usernames, metrics, links, and action buttons."""
        if not header_text:
            return None

        raw_lines = header_text.splitlines()

        lines: list[str] = []

        for raw_line in raw_lines:
            cleaned_line = self._clean_unicode_text(raw_line).strip()

            if not cleaned_line:
                continue

            lines.append(cleaned_line)

        external_hosts = {
            self._visible_url_text(str(link.url)) for link in external_links
        }

        bio_lines: list[str] = []

        normalized_username = username.lower()
        normalized_display_name = display_name.lower() if display_name else None

        for line in lines:
            normalized_line = line.lower()

            if normalized_line == normalized_username:
                continue

            if normalized_display_name and normalized_line == normalized_display_name:
                continue

            if normalized_line in self._IGNORED_HEADER_LINES:
                continue

            if self._is_stat_line(normalized_line):
                continue

            if self._looks_like_username_line(
                normalized_line,
                normalized_username,
            ):
                continue

            if self._looks_like_external_link_line(
                line=line,
                external_hosts=external_hosts,
            ):
                continue

            if self._looks_like_action_line(normalized_line):
                continue

            bio_lines.append(line)

        if not bio_lines:
            return None

        return "\n".join(bio_lines).strip() or None

    @staticmethod
    def _extract_bio_from_meta(
        description: str | None,
    ) -> str | None:
        """Extracts bio snippet from OpenGraph description if non-boilerplate."""
        if not description:
            return None

        normalized = description.strip()

        lower = normalized.lower()

        boilerplate_prefixes = (
            "see instagram photos and videos from",
            "instagram photos and videos from",
        )

        if any(lower.startswith(prefix) for prefix in boilerplate_prefixes):
            return None

        separator = " - "

        if separator not in normalized:
            return None

        _, raw_bio = normalized.split(
            separator,
            maxsplit=1,
        )

        bio = raw_bio.strip().strip('"').strip()

        return bio or None

    @staticmethod
    def _is_stat_line(
        line: str,
    ) -> bool:
        """Checks if a string matches profile metric patterns (e.g. '100 posts', '1.5k followers')."""
        patterns = (
            r"^[\d.,kmb]+\s+posts?$",
            r"^[\d.,kmb]+\s+followers?$",
            r"^[\d.,kmb]+\s+following$",
        )

        return any(
            re.fullmatch(
                pattern,
                line,
                flags=re.IGNORECASE,
            )
            is not None
            for pattern in patterns
        )

    @staticmethod
    def _looks_like_username_line(
        line: str,
        username: str,
    ) -> bool:
        """Checks if line equals '@username' handle format."""
        return line == f"@{username}"

    @staticmethod
    def _looks_like_action_line(
        line: str,
    ) -> bool:
        """Checks if line represents an action button label."""
        prefixes = (
            "follow ",
            "message ",
            "contact ",
        )

        return any(line.startswith(prefix) for prefix in prefixes)

    @staticmethod
    def _looks_like_external_link_line(
        *,
        line: str,
        external_hosts: set[str],
    ) -> bool:
        """Determines if a line matches known external link domains or URL schemas."""
        normalized_line = (
            line.lower().replace("https://", "").replace("http://", "").rstrip("/")
        )

        for external_text in external_hosts:
            normalized_external = (
                external_text.lower()
                .replace("https://", "")
                .replace("http://", "")
                .rstrip("/")
            )

            if normalized_external and normalized_external in normalized_line:
                return True

        if re.match(
            r"^https?://",
            line,
            flags=re.IGNORECASE,
        ):
            return True

        return False

    @staticmethod
    def _visible_url_text(
        url: str,
    ) -> str:
        """Converts a URL to its stripped host and path display representation."""
        parsed = urlparse(url)

        host = parsed.netloc.lower().removeprefix("www.")
        path = parsed.path.rstrip("/")

        return f"{host}{path}"

    def _extract_count(
        self,
        *,
        text: str,
        label: str,
    ) -> int:
        """Extracts a metric count preceding a label using regex."""
        pattern = rf"([\d.,]+(?:\.\d+)?" rf"\s*[KMB]?)" rf"\s+{re.escape(label)}"

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match is None:
            return 0

        return self._parse_compact_count(match.group(1))

    @staticmethod
    def _parse_compact_count(
        value: str,
    ) -> int:
        """Converts compact numerical strings with K/M/B suffixes to integers."""
        normalized = value.strip().lower().replace(",", "").replace(" ", "")

        multipliers: dict[str, int] = {
            "k": 1_000,
            "m": 1_000_000,
            "b": 1_000_000_000,
        }

        suffix = normalized[-1]

        if suffix in multipliers:
            number_part = normalized[:-1]
            number = float(number_part)

            return int(number * multipliers[suffix])

        return int(float(normalized))

    def _extract_external_links(
        self,
        page: Page,
    ) -> tuple[ExternalLink, ...]:
        """Extracts external URLs specifically located inside the profile header."""
        header = page.locator("header").first

        if header.count() == 0:
            return ()

        hrefs = header.locator("a[href]").evaluate_all("""
            elements => elements
                .map(element => element.href)
                .filter(Boolean)
            """)

        if not isinstance(hrefs, list):
            return ()

        links: list[ExternalLink] = []
        seen: set[str] = set()

        for raw_href in hrefs:
            if not isinstance(raw_href, str):
                continue

            href = self._unwrap_instagram_redirect(raw_href)

            if not self._is_external_url(href):
                continue

            normalized_href = href.strip()

            if not normalized_href or normalized_href in seen:
                continue

            try:
                external_link = ExternalLink(
                    url=HttpUrl(normalized_href),
                    title=None,
                    type=self._detect_link_type(normalized_href),
                )

            except ValueError:
                continue

            links.append(external_link)
            seen.add(normalized_href)

        return tuple(links)

    @staticmethod
    def _unwrap_instagram_redirect(
        url: str,
    ) -> str:
        """Extracts destination URL targets from Instagram redirect links (l.instagram.com)."""
        parsed = urlparse(url)

        hostname = (parsed.hostname or "").lower()

        if hostname != "l.instagram.com":
            return url

        query = parse_qs(parsed.query)

        target_values = query.get("u") or query.get("url")

        if not target_values:
            return url

        return unquote(target_values[0])

    @staticmethod
    def _is_external_url(
        url: str,
    ) -> bool:
        """Checks whether a URL points to an external destination rather than Meta/Instagram domains."""
        parsed = urlparse(url)

        if parsed.scheme not in {"http", "https"}:
            return False

        hostname = (parsed.hostname or "").lower()

        if not hostname:
            return False

        blocked_hosts = {
            "instagram.com",
            "www.instagram.com",
            "help.instagram.com",
            "about.instagram.com",
            "accountscenter.instagram.com",
            "l.instagram.com",
            "facebook.com",
            "www.facebook.com",
            "meta.com",
            "www.meta.com",
            "about.meta.com",
            "developers.facebook.com",
            "privacycenter.instagram.com",
            "threads.com",
            "www.threads.com",
        }

        return hostname not in blocked_hosts

    @staticmethod
    def _detect_link_type(
        url: str,
    ) -> ExternalLinkType:
        """Maps an external URL string to its ExternalLinkType enum variant."""
        normalized = url.lower()

        if "wa.me/" in normalized or "whatsapp.com/" in normalized:
            return ExternalLinkType.WHATSAPP

        if "t.me/" in normalized or "telegram.me/" in normalized:
            return ExternalLinkType.TELEGRAM

        link_in_bio_domains = (
            "takl.ink/",
            "linktr.ee/",
            "zil.ink/",
            "bio.link/",
        )

        if any(domain in normalized for domain in link_in_bio_domains):
            return ExternalLinkType.LINK_IN_BIO

        return ExternalLinkType.WEBSITE

    @staticmethod
    def _clean_unicode_text(
        value: str,
    ) -> str:
        """Strips invisible Unicode formatting and directional characters (e.g. RTL/LTR marks)."""
        invisible_categories = {"Cf"}

        cleaned = "".join(
            character
            for character in value
            if unicodedata.category(character) not in invisible_categories
        )

        return cleaned.strip()
