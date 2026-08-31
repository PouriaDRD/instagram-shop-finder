class ProfileFetchError(Exception):
    """Base exception for profile fetching."""


class ProfileNotFoundError(ProfileFetchError):
    """Raised when the requested profile does not exist."""


class PrivateProfileError(ProfileFetchError):
    """Raised when a profile is private."""


class RateLimitError(ProfileFetchError):
    """Raised when Instagram rate-limits requests."""
