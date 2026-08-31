from app.crawler.base import ProfileFetcher
from app.crawler.exceptions import ProfileNotFoundError
from app.models.external_link import (
    ExternalLink,
    ExternalLinkType,
)
from app.models.raw_profile import RawProfileData
from pydantic import HttpUrl


class MockProfileFetcher(ProfileFetcher):
    """Mock implementation of ProfileFetcher for local development and unit testing."""

    def __init__(self) -> None:
        """Initializes the mock fetcher with pre-populated dummy profile data."""
        self._profiles: dict[str, RawProfileData] = {
            "setayeshmasjedii": RawProfileData(
                username="setayeshmasjedii",
                display_name="ستایش مسجدی | setayeshmasjedi",
                bio=(
                    "Self-makeup training | content creator💄✨\n"
                    "میکاپ آرتیست خودت باش ❤️"
                ),
                external_links=(
                    ExternalLink(
                        # Wrapped with HttpUrl(...) to satisfy strict static type checkers (Pylance/Pyright)
                        url=HttpUrl("https://takl.ink/setayeshmasjedii"),
                        title="Links",
                        type=ExternalLinkType.LINK_IN_BIO,
                    ),
                ),
                followers_count=468_000,
                following_count=211,
                posts_count=331,
                is_public=True,
            ),
            "beauty_test": RawProfileData(
                username="beauty_test",
                display_name="Beauty Test",
                bio="لوازم آرایشی و مراقبت پوست",
                followers_count=4100,
                following_count=650,
                posts_count=190,
                is_public=True,
            ),
        }

    def fetch(self, username: str) -> RawProfileData:
        """Fetches a mock raw profile by username.

        Args:
            username: Target Instagram username (with or without leading '@').

        Returns:
            A deep copy of the matched RawProfileData instance.

        Raises:
            ValueError: If the sanitized username is empty.
            ProfileNotFoundError: If no matching mock profile exists.
        """
        normalized_username = self._normalize_username(username)

        profile = self._profiles.get(normalized_username)

        if profile is None:
            raise ProfileNotFoundError(
                f"Mock profile '@{normalized_username}' was not found."
            )

        # Return a deep copy to prevent callers from mutating mock state
        return profile.model_copy(deep=True)
