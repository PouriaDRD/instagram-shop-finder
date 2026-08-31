import re
import unicodedata
from typing import Final
from pydantic import HttpUrl
from urllib.parse import (
    parse_qs,
    unquote,
    urlparse,
)

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    Response,
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
from app.models.raw_profile import (
    RawProfileData,
)


class InstagramPlaywrightProfileFetcher(ProfileFetcher):
    """Playwright-based fetcher that launches a headless Chromium instance to scrape public Instagram profiles."""

    _BASE_URL: Final[str] = "https://www.instagram.com"

    _NAVIGATION_TIMEOUT_MS: Final[int] = 30_000
    _RENDER_TIMEOUT_MS: Final[int] = 15_000
    _BODY_TIMEOUT_MS: Final[int] = 8_000

    # Pattern for identifying visible, unhyperlinked domain names in raw text
    _VISIBLE_DOMAIN_PATTERN: Final[re.Pattern[str]] = re.compile(
        r"(?<![\w@.-])"
        r"(?P<domain>"
        r"(?:www\.)?"
        r"(?:"
        r"[a-zA-Z0-9]"
        r"(?:[a-zA-Z0-9-]*[a-zA-Z0-9])?"
        r"\."
        r")+"
        r"[a-zA-Z]{2,}"
        r"(?:/[^\s]*)?"
        r")",
        flags=re.IGNORECASE,
    )

    # Pattern to match pagination markers or truncated list indicators
    _AND_MORE_PATTERN: Final[re.Pattern[str]] = re.compile(
        r"\band\s+\d+\s+more\b",
        flags=re.IGNORECASE,
    )

    # Standard UI interaction text labels to ignore when extracting bio text
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
        """Launches a browser session to fetch public Instagram profile metadata.

        Args:
            username: Target Instagram handle (with or without leading '@').

        Returns:
            A RawProfileData instance containing extracted profile details.

        Raises:
            ValueError: If the normalized username is empty.
            ProfileNotFoundError: If Instagram returns an HTTP 404 status code.
            RateLimitError: If Instagram limits requests with HTTP 429.
            ProfileFetchError: On page timeouts, access restrictions, or unexpected errors.
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
        """Manages browser instance and context lifecycles during scraping execution.

        Args:
            playwright: Active Playwright sync runner.
            username: Normalized target profile handle.
            url: Fully qualified Instagram profile target URL.

        Returns:
            Extracted RawProfileData model instance.
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
        """Configures an isolated browser context with fixed desktop viewport and English locale."""
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
        """Navigates to profile URL, checks response status, waits for rendering, and parses metadata.

        Args:
            page: Active Browser Page object.
            username: Target handle.
            url: Target URL string.

        Returns:
            Populated RawProfileData object.

        Raises:
            ProfileNotFoundError: On HTTP 404 status.
            RateLimitError: On HTTP 429 status.
            ProfileFetchError: On access restrictions, challenge walls, or missing profile data.
        """
        response = self._navigate(
            page=page,
            url=url,
            username=username,
        )

        if response is not None:
            self._raise_for_status(
                status=response.status,
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
            title = page.title().strip() or None

        header_text = self._read_profile_header_text(page)

        if not title and not description and not header_text:
            raise ProfileFetchError(
                "Instagram rendered the page, " "but profile data was not found."
            )

        display_name = self._parse_display_name(title) if title else None

        # Use available text sources to extract public follower/following/post counts
        stats_source = description or header_text or body_text

        followers_count = self._extract_count(
            text=stats_source,
            label="followers",
        )

        following_count = self._extract_count(
            text=stats_source,
            label="following",
        )

        posts_count = self._extract_count(
            text=stats_source,
            label="posts",
        )

        external_links = self._extract_external_links(
            page=page,
            header_text=header_text,
            username=username,
        )

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
    ) -> Response | None:
        """Navigates to URL using 'commit' wait strategy to prevent hanging on background requests."""
        try:
            return page.goto(
                url,
                wait_until="commit",
                timeout=self._NAVIGATION_TIMEOUT_MS,
            )

        except PlaywrightTimeoutError:
            if page.url.startswith(self._BASE_URL):
                return None

            raise ProfileFetchError("Instagram page timed out for " f"'@{username}'.")

    @staticmethod
    def _raise_for_status(
        *,
        status: int,
        username: str,
    ) -> None:
        """Validates HTTP response status code and raises corresponding exceptions."""
        if status == 404:
            raise ProfileNotFoundError(
                f"Instagram profile '@{username}' was not found."
            )

        if status == 429:
            raise RateLimitError("Instagram returned HTTP 429 Too Many Requests.")

        if status in {
            401,
            403,
        }:
            raise ProfileFetchError(
                "Instagram blocked the request " f"with HTTP {status}."
            )

        if status >= 400:
            raise ProfileFetchError(f"Instagram returned HTTP {status}.")

    def _wait_for_profile_render(
        self,
        page: Page,
    ) -> None:
        """Waits for primary profile header DOM elements or OpenGraph meta tags to render."""
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
        """Extracts visible inner text of the body element."""
        try:
            return page.locator("body").inner_text(timeout=self._BODY_TIMEOUT_MS)

        except PlaywrightTimeoutError:
            return ""

    @staticmethod
    def _read_profile_header_text(
        page: Page,
    ) -> str:
        """Extracts inner text from the primary profile header container."""
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
        """Scans body text for known bot challenge markers or restricted-access messages."""
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
        """Reads content attribute value of a specific HTML meta element."""
        locator = page.locator(f'meta[property="{property_name}"]')

        if locator.count() == 0:
            return None

        content = locator.first.get_attribute("content")

        if not content:
            return None

        return content.strip() or None

    @classmethod
    def _parse_display_name(
        cls,
        title: str,
    ) -> str | None:
        """Strips standard Instagram branding suffixes and formatting from page title strings."""
        cleaned = re.sub(
            (r"\s*\(@[^)]+\)" r"\s*[•\-]\s*Instagram.*$"),
            "",
            title,
            flags=re.IGNORECASE,
        )

        return cls._clean_unicode_text(cleaned) or None

    def _extract_bio(
        self,
        *,
        username: str,
        display_name: str | None,
        header_text: str,
        description: str | None,
        external_links: tuple[
            ExternalLink,
            ...,
        ],
    ) -> str | None:
        """Extracts bio text, preferring visible header lines over meta description fallbacks."""
        result = self._extract_bio_from_header(
            username=username,
            display_name=display_name,
            header_text=header_text,
            external_links=external_links,
        )

        if result:
            return result

        return self._extract_bio_from_meta(description)

    def _extract_bio_from_header(
        self,
        *,
        username: str,
        display_name: str | None,
        header_text: str,
        external_links: tuple[
            ExternalLink,
            ...,
        ],
    ) -> str | None:
        """Parses bio lines out of header text by stripping usernames, stats, and action elements."""
        if not header_text:
            return None

        lines = self._clean_header_lines(header_text)

        external_texts = {
            self._visible_url_text(str(link.url)).lower() for link in external_links
        }

        normalized_username = username.lower()

        normalized_display_name = display_name.lower() if display_name else None

        bio_lines: list[str] = []
        bio_started = False

        for line in lines:
            normalized_line = line.lower()

            # Ignore line if it equals username handle
            if normalized_line in {
                normalized_username,
                f"@{normalized_username}",
            }:
                continue

            # Ignore line if it equals display name
            if normalized_display_name and normalized_line == normalized_display_name:
                continue

            # Ignore common action buttons and metric lines
            if normalized_line in self._IGNORED_HEADER_LINES:
                continue

            if self._is_stat_line(normalized_line):
                continue

            if self._looks_like_action_line(normalized_line):
                continue

            # Stop or skip on external links matching extracted targets
            if self._looks_like_external_link_line(
                line=line,
                external_link_texts=external_texts,
            ):
                if bio_started:
                    break

                continue

            if self._AND_MORE_PATTERN.search(line):
                if bio_started:
                    break

                continue

            if self._is_probable_highlight_boundary(
                line=line,
                bio_started=bio_started,
            ):
                if bio_started:
                    break

                continue

            bio_lines.append(line)

            bio_started = True

        if not bio_lines:
            return None

        return "\n".join(bio_lines).strip() or None

    @classmethod
    def _clean_header_lines(
        cls,
        header_text: str,
    ) -> list[str]:
        """Strips invisible Unicode characters and removes empty lines from raw header text."""
        return [
            cleaned
            for raw in header_text.splitlines()
            if (cleaned := cls._clean_unicode_text(raw))
        ]

    @staticmethod
    def _extract_bio_from_meta(
        description: str | None,
    ) -> str | None:
        """Parses bio text from meta description when header extraction yields no results."""
        if not description:
            return None

        normalized = description.strip()

        if normalized.lower().startswith(
            (
                "see instagram photos and videos from",
                "instagram photos and videos from",
            )
        ):
            return None

        if " - " not in normalized:
            return None

        _, bio = normalized.split(
            " - ",
            maxsplit=1,
        )

        return bio.strip().strip('"').strip() or None

    @staticmethod
    def _is_stat_line(
        line: str,
    ) -> bool:
        """Determines if a line matches post, follower, or following count patterns."""
        return any(
            re.fullmatch(
                pattern,
                line,
                flags=re.IGNORECASE,
            )
            is not None
            for pattern in (
                r"^[\d.,kmb]+\s+posts?$",
                r"^[\d.,kmb]+\s+followers?$",
                r"^[\d.,kmb]+\s+following$",
            )
        )

    @staticmethod
    def _looks_like_action_line(
        line: str,
    ) -> bool:
        """Checks if a string represents an action button label."""
        return any(
            line.startswith(prefix)
            for prefix in (
                "follow ",
                "message ",
                "contact ",
            )
        )

    @staticmethod
    def _looks_like_external_link_line(
        *,
        line: str,
        external_link_texts: set[str],
    ) -> bool:
        """Checks if a line matches extracted external link domain representations."""
        normalized = (
            line.lower()
            .replace("https://", "")
            .replace("http://", "")
            .removeprefix("www.")
            .rstrip("/")
        )

        return any(
            external_text.replace("https://", "")
            .replace("http://", "")
            .removeprefix("www.")
            .rstrip("/")
            in normalized
            for external_text in external_link_texts
            if external_text
        )

    @staticmethod
    def _is_probable_highlight_boundary(
        *,
        line: str,
        bio_started: bool,
    ) -> bool:
        """Identifies numeric story highlight titles after bio text parsing has started."""
        if not bio_started:
            return False

        return (
            re.fullmatch(
                r"[۰-۹٠-٩\d]+",
                line.strip(),
            )
            is not None
        )

    @staticmethod
    def _visible_url_text(
        url: str,
    ) -> str:
        """Converts a full URL string into its core netloc and path representation."""
        parsed = urlparse(url)

        return parsed.netloc.removeprefix("www.") + parsed.path.rstrip("/")

    def _extract_count(
        self,
        *,
        text: str,
        label: str,
    ) -> int:
        """Extracts metric count preceding a label using regular expressions."""
        match = re.search(
            (rf"([\d.,]+(?:\.\d+)?" rf"\s*[KMB]?)" rf"\s+{re.escape(label)}"),
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
        """Converts compact numerical strings with K/M/B multipliers into whole integers."""
        normalized = value.strip().lower().replace(",", "").replace(" ", "")

        multipliers = {
            "k": 1_000,
            "m": 1_000_000,
            "b": 1_000_000_000,
        }

        suffix = normalized[-1]

        if suffix in multipliers:
            return int(float(normalized[:-1]) * multipliers[suffix])

        return int(float(normalized))

    def _extract_external_links(
        self,
        *,
        page: Page,
        header_text: str,
        username: str,
    ) -> tuple[ExternalLink, ...]:
        """Extracts, unwraps, and normalizes external links from header anchors and visible text."""
        urls: list[str] = []

        header = page.locator("header").first

        if header.count() > 0:
            hrefs = header.locator("a[href]").evaluate_all("""
                elements => elements
                    .map(element => element.href)
                    .filter(Boolean)
                """)

            if isinstance(
                hrefs,
                list,
            ):
                for raw_href in hrefs:
                    if isinstance(
                        raw_href,
                        str,
                    ):
                        urls.append(self._unwrap_instagram_redirect(raw_href))

        urls.extend(
            self._extract_visible_urls(
                text=header_text,
                username=username,
            )
        )

        links: list[ExternalLink] = []

        seen: set[str] = set()

        for url in urls:
            normalized = url.strip()

            if not normalized or not self._is_external_url(normalized):
                continue

            canonical_key = self._canonical_url_key(normalized)

            if not canonical_key or canonical_key in seen:
                continue

            try:
                link = ExternalLink(
                    url=HttpUrl(normalized),
                    title=None,
                    type=self._detect_link_type(normalized),
                )

            except ValueError:
                continue

            links.append(link)

            seen.add(canonical_key)

        return tuple(links)

    def _extract_visible_urls(
        self,
        *,
        text: str,
        username: str,
    ) -> list[str]:
        """Scans raw header text for unhyperlinked visible domains and prepends HTTPS scheme."""
        urls: list[str] = []

        normalized_username = username.strip().lstrip("@").lower()

        for match in self._VISIBLE_DOMAIN_PATTERN.finditer(text):
            domain = match.group("domain").rstrip(".,،؛:!?)")

            if not domain:
                continue

            if domain.lower().startswith(
                (
                    "http://",
                    "https://",
                )
            ):
                url = domain
            else:
                url = f"https://{domain}"

            parsed = urlparse(url)

            hostname = (parsed.hostname or "").lower()

            # Exclude domains matching user's own handle
            if hostname == normalized_username:
                continue

            urls.append(url)

        return urls

    @staticmethod
    def _canonical_url_key(
        url: str,
    ) -> str:
        """Generates a normalized deduplication key for a given URL string."""
        parsed = urlparse(url)

        hostname = (parsed.hostname or "").lower()

        if not hostname:
            return ""

        hostname = hostname.removeprefix("www.")

        path = parsed.path.rstrip("/")

        query = f"?{parsed.query}" if parsed.query else ""

        return f"{hostname}{path}{query}"

    @staticmethod
    def _unwrap_instagram_redirect(
        url: str,
    ) -> str:
        """Extracts true destination URL from Instagram redirect wrapper links (l.instagram.com)."""
        parsed = urlparse(url)

        if (parsed.hostname or "").lower() != "l.instagram.com":
            return url

        query = parse_qs(parsed.query)

        targets = query.get("u") or query.get("url")

        if not targets:
            return url

        return unquote(targets[0])

    @staticmethod
    def _is_external_url(
        url: str,
    ) -> bool:
        """Determines whether a URL targets external domains rather than Meta/Instagram hosts."""
        parsed = urlparse(url)

        if parsed.scheme not in {
            "http",
            "https",
        }:
            return False

        hostname = (parsed.hostname or "").lower()

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

        return bool(hostname and hostname not in blocked_hosts)

    @staticmethod
    def _detect_link_type(
        url: str,
    ) -> ExternalLinkType:
        """Maps an external URL string to its ExternalLinkType enum category."""
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

    @staticmethod
    def _clean_unicode_text(
        value: str,
    ) -> str:
        """Strips invisible Unicode formatting characters (e.g., directional control characters)."""
        return "".join(
            character for character in value if unicodedata.category(character) != "Cf"
        ).strip()
