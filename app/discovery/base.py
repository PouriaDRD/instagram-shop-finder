from abc import ABC, abstractmethod


class DiscoverySource(ABC):
    """
    Source responsible only for discovering candidate Instagram usernames.

    A discovery source does not decide whether a profile is a shop.
    It only returns possible public Instagram usernames.

    The existing crawler/classifier pipeline performs final verification.
    """

    @abstractmethod
    def discover(self, *, query: str, limit: int) -> list[str]:
        raise NotImplementedError
