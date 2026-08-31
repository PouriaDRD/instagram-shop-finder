from abc import ABC, abstractmethod

from app.models.raw_profile import RawProfileData


class ProfileFetcher(ABC):

    @abstractmethod
    def fetch(self, username: str) -> RawProfileData:
        raise NotImplementedError

    @staticmethod
    def _normalize_username(username: str) -> str:
        """Sanitizes username inputs by trimming whitespace, lowercasing, and removing leading '@' symbols.

        Args:
            username: The raw username string to normalize.

        Returns:
            A clean lowercase username string.

        Raises:
            ValueError: If the normalized username is empty.
        """
        normalized = username.strip()

        if normalized.startswith("@"):
            normalized = normalized[1:]

        normalized = normalized.lower()

        if not normalized:
            raise ValueError("Instagram username cannot be empty.")

        return normalized
