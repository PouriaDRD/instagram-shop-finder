import re
import unicodedata
from typing import Final
from urllib.parse import (
    parse_qs,
    unquote,
    urlparse,
)

from pydantic import HttpUrl
from playwright.sync_api import (
    Browser,
    BrowserContext,
    Locator,
    Page,
    Playwright,
    Response,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

from app.classifiers.link_classifier import LinkClassifier
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
    """
    Playwright-based fetcher for public Instagram profile metadata.

    Supports:
    - reusable browser sessions
    - public profile metadata extraction
    - expanded external links
    - Instagram profile links
    - sign-up dialog dismissal
    - DOM-aware highlight exclusion from profile bio
    """

    _BASE_URL: Final[str] = "https://www.instagram.com"

    _NAVIGATION_TIMEOUT_MS: Final[int] = 30_000
    _RENDER_TIMEOUT_MS: Final[int] = 15_000
    _BODY_TIMEOUT_MS: Final[int] = 8_000

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

    _AND_MORE_PATTERN: Final[re.Pattern[str]] = re.compile(
        r"\band\s+\d+\s+more\b",
        flags=re.IGNORECASE,
    )

    _MORE_LINKS_PATTERN: Final[re.Pattern[str]] = re.compile(
        r"(?:and\s+)?\d+\s+more",
        flags=re.IGNORECASE,
    )

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

    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    @property
    def is_open(self) -> bool:
        return (
            self._playwright is not None
            and self._browser is not None
            and self._context is not None
        )

    def open(self) -> None:
        if self.is_open:
            return

        playwright = sync_playwright().start()

        try:
            browser = self._launch_browser(playwright)

            context = self._create_context(browser)

        except Exception:
            playwright.stop()
            raise

        self._playwright = playwright
        self._browser = browser
        self._context = context

    def close(self) -> None:
        context = self._context
        browser = self._browser
        playwright = self._playwright

        self._context = None
        self._browser = None
        self._playwright = None

        if context is not None:
            context.close()

        if browser is not None:
            browser.close()

        if playwright is not None:
            playwright.stop()

    def fetch(
        self,
        username: str,
    ) -> RawProfileData:
        normalized_username = self._normalize_username(username)

        url = f"{self._BASE_URL}/" f"{normalized_username}/"

        if self._context is not None:
            return self._fetch_with_context(
                context=self._context,
                username=normalized_username,
                url=url,
            )

        try:
            with sync_playwright() as playwright:
                browser = self._launch_browser(playwright)

                try:
                    context = self._create_context(browser)

                    try:
                        return self._fetch_with_context(
                            context=context,
                            username=normalized_username,
                            url=url,
                        )

                    finally:
                        context.close()

                finally:
                    browser.close()

        except ProfileFetchError:
            raise

        except Exception as exc:
            raise ProfileFetchError(
                "Unexpected browser error while "
                f"fetching '@{normalized_username}': "
                f"{exc}"
            ) from exc

    def _fetch_with_context(
        self,
        *,
        context: BrowserContext,
        username: str,
        url: str,
    ) -> RawProfileData:
        page = context.new_page()

        try:
            return self._fetch_page(
                page=page,
                username=username,
                url=url,
            )

        finally:
            page.close()

    @staticmethod
    def _launch_browser(
        playwright: Playwright,
    ) -> Browser:
        return playwright.chromium.launch(
            headless=True,
        )

    @staticmethod
    def _create_context(
        browser: Browser,
    ) -> BrowserContext:
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
        response = self._navigate(
            page=page,
            url=url,
            username=username,
        )

        if response is not None:
            self._raise_for_response(
                response=response,
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

        highlight_titles = self._read_highlight_titles(page)

        if not title and not description and not header_text:
            raise ProfileFetchError(
                "Instagram rendered the page, " "but profile data was not found."
            )

        display_name = self._parse_display_name(title) if title else None

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
            highlight_titles=highlight_titles,
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

    @classmethod
    def _raise_for_response(
        cls,
        *,
        response: Response,
        username: str,
    ) -> None:
        status = response.status

        if status == 404:
            raise ProfileNotFoundError(
                f"Instagram profile " f"'@{username}' was not found."
            )

        if status == 429:
            retry_after = cls._read_retry_after(response)

            raise RateLimitError(
                "Instagram returned HTTP 429 " "Too Many Requests.",
                retry_after_seconds=retry_after,
            )

        if status in {
            401,
            403,
        }:
            raise ProfileFetchError(
                "Instagram blocked the request " f"with HTTP {status}."
            )

        if status >= 400:
            raise ProfileFetchError(f"Instagram returned HTTP {status}.")

    @staticmethod
    def _read_retry_after(
        response: Response,
    ) -> float | None:
        raw_value = response.headers.get("retry-after")

        if not raw_value:
            return None

        try:
            value = float(raw_value.strip())

        except ValueError:
            return None

        if value <= 0:
            return None

        return value

    def _wait_for_profile_render(
        self,
        page: Page,
    ) -> None:
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
        try:
            return page.locator("body").inner_text(timeout=self._BODY_TIMEOUT_MS)

        except PlaywrightTimeoutError:
            return ""

    @staticmethod
    def _read_profile_header_text(
        page: Page,
    ) -> str:
        header = page.locator("header").first

        if header.count() == 0:
            return ""

        try:
            return header.inner_text(timeout=5_000).strip()

        except PlaywrightTimeoutError:
            return ""

    @classmethod
    def _read_highlight_titles(
        cls,
        page: Page,
    ) -> tuple[str, ...]:
        """
        Read visible Instagram Highlight titles directly
        from their /stories/highlights/... anchors.

        This gives us a reliable boundary between the
        real profile bio and the Highlight carousel.
        """
        header = page.locator("header").first

        if header.count() == 0:
            return ()

        anchors = header.locator('a[href*="/stories/highlights/"]')

        try:
            raw_titles = anchors.evaluate_all("""
                elements => elements.map(
                    element => (
                        element.innerText ||
                        element.textContent ||
                        ""
                    ).trim()
                )
                """)

        except Exception:
            return ()

        if not isinstance(
            raw_titles,
            list,
        ):
            return ()

        titles: list[str] = []
        seen: set[str] = set()

        for raw_title in raw_titles:
            if not isinstance(
                raw_title,
                str,
            ):
                continue

            title = cls._clean_unicode_text(raw_title)

            if not title:
                continue

            normalized = title.casefold()

            if normalized in seen:
                continue

            seen.add(normalized)

            titles.append(title)

        return tuple(titles)

    @staticmethod
    def _detect_blocked_page(
        body_text: str,
    ) -> None:
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
        external_links: tuple[ExternalLink, ...],
        highlight_titles: tuple[str, ...] = (),
    ) -> str | None:
        result = self._extract_bio_from_header(
            username=username,
            display_name=display_name,
            header_text=header_text,
            external_links=external_links,
            highlight_titles=highlight_titles,
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
        external_links: tuple[ExternalLink, ...],
        highlight_titles: tuple[str, ...] = (),
    ) -> str | None:
        if not header_text:
            return None

        lines = self._clean_header_lines(header_text)

        external_texts = {
            self._visible_url_text(str(link.url)).lower() for link in external_links
        }

        normalized_username = username.lower()

        normalized_display_name = display_name.lower() if display_name else None

        normalized_highlight_titles = {
            self._normalize_comparison_text(title)
            for title in highlight_titles
            if title
        }

        bio_lines: list[str] = []
        bio_started = False

        for line in lines:
            normalized_line = line.lower()

            comparison_line = self._normalize_comparison_text(line)

            # Most reliable bio/highlight boundary:
            # title was extracted from a real
            # /stories/highlights/... anchor.
            if bio_started and comparison_line in normalized_highlight_titles:
                break

            if normalized_line in {
                normalized_username,
                f"@{normalized_username}",
            }:
                continue

            if normalized_display_name and normalized_line == normalized_display_name:
                continue

            if normalized_line in self._IGNORED_HEADER_LINES:
                continue

            if self._is_stat_line(normalized_line):
                continue

            if self._looks_like_action_line(normalized_line):
                continue

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
        return [
            cleaned
            for raw in header_text.splitlines()
            if (cleaned := cls._clean_unicode_text(raw))
        ]

    @staticmethod
    def _normalize_comparison_text(
        value: str,
    ) -> str:
        translation_table = str.maketrans(
            {
                "ي": "ی",
                "ى": "ی",
                "ك": "ک",
                "ۀ": "ه",
                "ة": "ه",
                "\u200c": " ",
                "\u200f": "",
                "\u200e": "",
            }
        )

        normalized = value.translate(translation_table).casefold()

        normalized = re.sub(
            r"\s+",
            " ",
            normalized,
        )

        return normalized.strip()

    @staticmethod
    def _extract_bio_from_meta(
        description: str | None,
    ) -> str | None:
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
        normalized = (
            line.lower()
            .replace(
                "https://",
                "",
            )
            .replace(
                "http://",
                "",
            )
            .removeprefix("www.")
            .rstrip("/")
        )

        return any(
            external_text.replace(
                "https://",
                "",
            )
            .replace(
                "http://",
                "",
            )
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
        parsed = urlparse(url)

        return parsed.netloc.removeprefix("www.") + parsed.path.rstrip("/")

    def _extract_count(
        self,
        *,
        text: str,
        label: str,
    ) -> int:
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
        normalized = (
            value.strip()
            .lower()
            .replace(
                ",",
                "",
            )
            .replace(
                " ",
                "",
            )
        )

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
        candidates: list[tuple[str, str | None]] = []

        header = page.locator("header").first

        if header.count() > 0:
            candidates.extend(
                self._collect_anchor_candidates(
                    container=header,
                )
            )

            candidates.extend(
                self._collect_expanded_link_candidates(
                    page=page,
                    header=header,
                )
            )

        for visible_url in self._extract_visible_urls(
            text=header_text,
            username=username,
        ):
            candidates.append(
                (
                    visible_url,
                    None,
                )
            )

        links: list[ExternalLink] = []

        seen: set[str] = set()

        for raw_url, raw_title in candidates:
            normalized_url = self._unwrap_instagram_redirect(raw_url).strip()

            if not normalized_url or not self._is_external_url(normalized_url):
                continue

            canonical_key = self._canonical_url_key(normalized_url)

            if not canonical_key or canonical_key in seen:
                continue

            title = self._clean_link_title(raw_title)

            try:
                link = ExternalLink(
                    url=HttpUrl(normalized_url),
                    title=title,
                    type=self._detect_link_type(
                        normalized_url,
                        title,
                    ),
                )

            except ValueError:
                continue

            links.append(link)

            seen.add(canonical_key)

        if header.count() > 0:
            instagram_links = self._extract_instagram_profile_links(
                header=header,
                current_username=username,
            )

            for link in instagram_links:
                canonical_key = self._canonical_url_key(str(link.url))

                if not canonical_key or canonical_key in seen:
                    continue

                links.append(link)

                seen.add(canonical_key)

        return tuple(links)

    def _collect_expanded_link_candidates(
        self,
        *,
        page: Page,
        header: Locator,
    ) -> list[tuple[str, str | None]]:
        if header.count() == 0:
            return []

        self._dismiss_signup_dialog_if_possible(page)

        if self._has_blocking_signup_dialog(page):
            return []

        trigger = self._find_more_links_trigger(header)

        if trigger is None:
            return []

        before_keys = self._collect_page_external_url_keys(page)

        try:
            trigger.scroll_into_view_if_needed(timeout=2_000)

        except PlaywrightTimeoutError:
            pass

        try:
            trigger.click(
                timeout=5_000,
            )

        except PlaywrightTimeoutError:
            return []

        page.wait_for_timeout(500)

        dialog_candidates = self._collect_from_visible_link_dialogs(page)

        if dialog_candidates:
            return dialog_candidates

        fallback_candidates = self._collect_anchor_candidates(
            container=page.locator("body"),
            visible_only=True,
        )

        new_candidates: list[tuple[str, str | None]] = []

        for raw_url, title in fallback_candidates:
            normalized_url = self._unwrap_instagram_redirect(raw_url)

            if not self._is_external_url(normalized_url):
                continue

            key = self._canonical_url_key(normalized_url)

            if key and key not in before_keys:
                new_candidates.append(
                    (
                        raw_url,
                        title,
                    )
                )

        return new_candidates

    def _dismiss_signup_dialog_if_possible(
        self,
        page: Page,
    ) -> bool:
        dialogs = page.locator('[role="dialog"]:visible')

        try:
            count = dialogs.count()

        except Exception:
            return False

        for index in range(count):
            dialog = dialogs.nth(index)

            if not self._looks_like_signup_dialog(dialog):
                continue

            close_button = self._find_dialog_close_button(dialog)

            if close_button is None:
                return False

            try:
                close_button.click(timeout=3_000)

            except PlaywrightTimeoutError:
                return False

            try:
                dialog.wait_for(
                    state="hidden",
                    timeout=3_000,
                )

            except PlaywrightTimeoutError:
                return False

            return True

        return False

    def _has_blocking_signup_dialog(
        self,
        page: Page,
    ) -> bool:
        dialogs = page.locator('[role="dialog"]:visible')

        try:
            count = dialogs.count()

        except Exception:
            return False

        for index in range(count):
            dialog = dialogs.nth(index)

            if self._looks_like_signup_dialog(dialog):
                return True

        return False

    @staticmethod
    def _looks_like_signup_dialog(
        dialog: Locator,
    ) -> bool:
        try:
            text = dialog.inner_text(timeout=1_000).lower()

        except Exception:
            return False

        return "sign up" in text and "log in" in text

    def _find_dialog_close_button(
        self,
        dialog: Locator,
    ) -> Locator | None:
        selectors = (
            'button[aria-label="Close"]',
            '[role="button"][aria-label="Close"]',
            'button[aria-label="close"]',
            '[role="button"][aria-label="close"]',
        )

        for selector in selectors:
            candidates = dialog.locator(selector)

            try:
                count = candidates.count()

            except Exception:
                count = 0

            for index in range(count):
                candidate = candidates.nth(index)

                try:
                    if candidate.is_visible():
                        return candidate

                except Exception:
                    continue

        svg_candidates = dialog.locator(
            ('svg[aria-label="Close"], ' 'svg[aria-label="close"]')
        )

        try:
            count = svg_candidates.count()

        except Exception:
            count = 0

        for index in range(count):
            svg = svg_candidates.nth(index)

            try:
                if not svg.is_visible():
                    continue

            except Exception:
                continue

            button = svg.locator(
                ("xpath=ancestor::*[" "self::button " "or @role='button'" "][1]")
            )

            if button.count() == 0:
                continue

            try:
                if button.first.is_visible():
                    return button.first

            except Exception:
                continue

        text_buttons = dialog.get_by_role(
            "button",
            name=re.compile(
                r"^close$",
                flags=re.IGNORECASE,
            ),
        )

        try:
            count = text_buttons.count()

        except Exception:
            count = 0

        for index in range(count):
            candidate = text_buttons.nth(index)

            try:
                if candidate.is_visible():
                    return candidate

            except Exception:
                continue

        return None

    def _find_more_links_trigger(
        self,
        header: Locator,
    ) -> Locator | None:
        link_icons = header.locator(
            (
                'svg[aria-label="Link icon"], '
                'svg[aria-label="Links icon"], '
                'svg[aria-label="link icon"]'
            )
        )

        try:
            icon_count = link_icons.count()

        except Exception:
            icon_count = 0

        for index in range(icon_count):
            icon = link_icons.nth(index)

            try:
                if not icon.is_visible():
                    continue

            except Exception:
                continue

            clickable = icon.locator(
                ("xpath=ancestor::*[" "self::button " "or @role='button'" "][1]")
            )

            if clickable.count() == 0:
                continue

            candidate = clickable.first

            try:
                if candidate.is_visible():
                    return candidate

            except Exception:
                continue

        buttons = header.locator("button").filter(has_text=(self._MORE_LINKS_PATTERN))

        try:
            count = buttons.count()

        except Exception:
            count = 0

        for index in range(count):
            candidate = buttons.nth(index)

            try:
                if candidate.is_visible():
                    return candidate

            except Exception:
                continue

        role_buttons = header.locator('[role="button"]').filter(
            has_text=(self._MORE_LINKS_PATTERN)
        )

        try:
            count = role_buttons.count()

        except Exception:
            count = 0

        for index in range(count):
            candidate = role_buttons.nth(index)

            try:
                if candidate.is_visible():
                    return candidate

            except Exception:
                continue

        return None

    def _collect_from_visible_link_dialogs(
        self,
        page: Page,
    ) -> list[tuple[str, str | None]]:
        dialogs = page.locator('[role="dialog"]:visible')

        try:
            count = dialogs.count()

        except Exception:
            return []

        for index in reversed(range(count)):
            dialog = dialogs.nth(index)

            if self._looks_like_signup_dialog(dialog):
                continue

            candidates = self._collect_anchor_candidates(
                container=dialog,
                visible_only=True,
            )

            external_candidates: list[tuple[str, str | None]] = []

            for raw_url, title in candidates:
                normalized_url = self._unwrap_instagram_redirect(raw_url)

                if self._is_external_url(normalized_url):
                    external_candidates.append(
                        (
                            raw_url,
                            title,
                        )
                    )

            if external_candidates:
                return external_candidates

        return []

    def _collect_page_external_url_keys(
        self,
        page: Page,
    ) -> set[str]:
        candidates = self._collect_anchor_candidates(
            container=page.locator("body"),
            visible_only=True,
        )

        result: set[str] = set()

        for raw_url, _ in candidates:
            normalized_url = self._unwrap_instagram_redirect(raw_url)

            if not self._is_external_url(normalized_url):
                continue

            key = self._canonical_url_key(normalized_url)

            if key:
                result.add(key)

        return result

    def _collect_anchor_candidates(
        self,
        *,
        container: Locator,
        visible_only: bool = False,
    ) -> list[tuple[str, str | None]]:
        if container.count() == 0:
            return []

        selector = "a[href]:visible" if visible_only else "a[href]"

        raw_candidates = container.locator(selector).evaluate_all("""
                elements => elements.map(
                    element => ({
                        href:
                            element.href || "",
                        text:
                            (
                                element.innerText ||
                                element.textContent ||
                                ""
                            ).trim()
                    })
                )
                """)

        candidates: list[tuple[str, str | None]] = []

        if not isinstance(
            raw_candidates,
            list,
        ):
            return candidates

        for item in raw_candidates:
            if not isinstance(
                item,
                dict,
            ):
                continue

            href = item.get("href")

            text = item.get("text")

            if not isinstance(
                href,
                str,
            ):
                continue

            href = href.strip()

            if not href:
                continue

            title: str | None = None

            if isinstance(
                text,
                str,
            ):
                title = text.strip() or None

            candidates.append(
                (
                    href,
                    title,
                )
            )

        return candidates

    def _extract_instagram_profile_links(
        self,
        *,
        header: Locator,
        current_username: str,
    ) -> tuple[ExternalLink, ...]:
        raw_candidates = self._collect_anchor_candidates(
            container=header,
        )

        links: list[ExternalLink] = []

        seen: set[str] = set()

        normalized_current_username = current_username.strip().lstrip("@").lower()

        blocked_first_segments = {
            "accounts",
            "about",
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

        username_pattern = re.compile(r"^[a-zA-Z0-9._]+$")

        for raw_url, raw_title in raw_candidates:
            parsed = urlparse(raw_url)

            hostname = (parsed.hostname or "").lower()

            if hostname not in {
                "instagram.com",
                "www.instagram.com",
            }:
                continue

            path_parts = [part for part in parsed.path.split("/") if part]

            if len(path_parts) != 1:
                continue

            linked_username = path_parts[0].strip().lower()

            if not linked_username:
                continue

            if linked_username == normalized_current_username:
                continue

            if linked_username in blocked_first_segments:
                continue

            if username_pattern.fullmatch(linked_username) is None:
                continue

            canonical_url = "https://www.instagram.com/" f"{linked_username}/"

            if linked_username in seen:
                continue

            title = self._clean_link_title(raw_title)

            if not title:
                title = f"@{linked_username}"

            try:
                link = ExternalLink(
                    url=HttpUrl(canonical_url),
                    title=title,
                    type=(ExternalLinkType.INSTAGRAM),
                )

            except ValueError:
                continue

            links.append(link)

            seen.add(linked_username)

        return tuple(links)

    @classmethod
    def _clean_link_title(
        cls,
        value: str | None,
    ) -> str | None:
        if not value:
            return None

        cleaned = cls._clean_unicode_text(value)

        if not cleaned:
            return None

        cleaned = cls._AND_MORE_PATTERN.sub(
            "",
            cleaned,
        )

        cleaned = re.sub(
            r"\s+",
            " ",
            cleaned,
        ).strip(" ,،|-")

        if not cleaned:
            return None

        normalized_title = (
            cleaned.lower()
            .replace(
                "https://",
                "",
            )
            .replace(
                "http://",
                "",
            )
            .removeprefix("www.")
            .rstrip("/")
        )

        if re.fullmatch(
            (r"[a-z0-9.-]+" r"\.[a-z]{2,}" r"(?:/[^\s]*)?"),
            normalized_title,
            flags=re.IGNORECASE,
        ):
            return None

        return cleaned

    def _extract_visible_urls(
        self,
        *,
        text: str,
        username: str,
    ) -> list[str]:
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

            if hostname == normalized_username:
                continue

            urls.append(url)

        return urls

    @staticmethod
    def _canonical_url_key(
        url: str,
    ) -> str:
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
            "privacycenter.instagram.com",
            "facebook.com",
            "www.facebook.com",
            "meta.com",
            "www.meta.com",
            "about.meta.com",
            "meta.ai",
            "www.meta.ai",
            "developers.facebook.com",
        }

        return bool(hostname and hostname not in blocked_hosts)

    @staticmethod
    def _detect_link_type(
        url: str,
        title: str | None = None,
    ) -> ExternalLinkType:
        return LinkClassifier.classify(
            url=url,
            title=title,
        )

    @staticmethod
    def _clean_unicode_text(
        value: str,
    ) -> str:
        return "".join(
            character for character in value if unicodedata.category(character) != "Cf"
        ).strip()

    def __enter__(
        self,
    ) -> "InstagramPlaywrightProfileFetcher":
        self.open()

        return self

    def __exit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        self.close()
