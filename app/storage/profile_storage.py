from .base_storage import JsonFileStorage
from app.models.profile import InstagramProfile


class ProfileStorage(JsonFileStorage[InstagramProfile]):
    """Typed storage implementation for InstagramProfile domain models."""

    def get_all(self) -> list[InstagramProfile]:
        return [InstagramProfile.model_validate(item) for item in self._read_raw()]

    def get_by_username(self, username: str) -> InstagramProfile | None:
        normalized = self._normalize_username(username)

        for profile in self.get_all():
            if profile.username.lower() == normalized:
                return profile

        return None

    def save(self, profile: InstagramProfile) -> None:
        raw_items = self._read_raw()

        profiles_by_username = {
            str(item.get("username", "")).lower(): item for item in raw_items
        }

        profiles_by_username[profile.username.lower()] = profile.model_dump(mode="json")

        self._write_raw(list(profiles_by_username.values()))
