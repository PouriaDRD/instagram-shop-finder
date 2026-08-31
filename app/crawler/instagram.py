from typing import Final

import instaloader

from app.crawler.base import ProfileFetcher
from app.crawler.exceptions import (
    ProfileFetchError,
    ProfileNotFoundError,
    RateLimitError,
)
from app.models.raw_profile import RawProfileData


class InstagramProfileFetcher(ProfileFetcher):
    """Instaloader-based implementation of ProfileFetcher."""

    _USER_AGENT: Final[str] = (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    )

    def __init__(self) -> None:
        """Initializes Instaloader with custom context headers and minimal downloads."""
        self._loader = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            quiet=True,
            max_connection_attempts=1,
            request_timeout=15,
        )

        self._loader.context.user_agent = self._USER_AGENT

    def fetch(self, username: str) -> RawProfileData:
        """Fetches raw public profile data using Instaloader.

        Args:
            username: Target Instagram username.

        Returns:
            A RawProfileData model matching the ProfileFetcher interface.

        Raises:
            ValueError: If the normalized username is empty.
            ProfileNotFoundError: If the profile does not exist.
            RateLimitError: If Instagram limits requests.
            ProfileFetchError: On network or Instaloader errors.
        """
        normalized_username = self._normalize_username(username)

        try:
            profile = instaloader.Profile.from_username(
                self._loader.context,
                normalized_username,
            )

        except instaloader.exceptions.ProfileNotExistsException as exc:
            raise ProfileNotFoundError(
                f"Instagram profile '@{normalized_username}' was not found."
            ) from exc

        except instaloader.exceptions.TooManyRequestsException as exc:
            raise RateLimitError(
                "Instagram returned HTTP 429 Too Many Requests."
            ) from exc

        except instaloader.exceptions.ConnectionException as exc:
            message = str(exc).lower()

            if "429" in message or "too many requests" in message:
                raise RateLimitError(
                    "Instagram returned HTTP 429 Too Many Requests."
                ) from exc

            raise ProfileFetchError(
                f"Could not fetch '@{normalized_username}': {exc}"
            ) from exc

        except instaloader.exceptions.InstaloaderException as exc:
            raise ProfileFetchError(
                f"Instagram error while fetching '@{normalized_username}': {exc}"
            ) from exc

        return RawProfileData(
            username=profile.username,
            display_name=profile.full_name or None,
            bio=profile.biography or None,
            followers_count=profile.followers,
            following_count=profile.followees,
            posts_count=profile.mediacount,
            is_public=not profile.is_private,
        )
