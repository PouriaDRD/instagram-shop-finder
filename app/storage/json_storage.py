import json
from pathlib import Path

from app.models.profile import InstagramProfile


class JsonProfileStorage:

    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path

        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        self._file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if not self._file_path.exists():
            self._file_path.write_text(
                "[]",
                encoding="utf-8",
            )

    def get_all(self) -> list[InstagramProfile]:
        raw_data = json.loads(
            self._file_path.read_text(
                encoding="utf-8",
            )
        )

        return [InstagramProfile.model_validate(item) for item in raw_data]

    def get_by_username(self, username: str) -> InstagramProfile | None:

        normalized_username = username.lower()

        for profile in self.get_all():
            if profile.username.lower() == normalized_username:
                return profile

        return None

    def save(self, profile: InstagramProfile) -> None:

        profiles = self.get_all()

        profiles_by_username = {item.username.lower(): item for item in profiles}

        profiles_by_username[profile.username.lower()] = profile

        serialized = [
            item.model_dump(
                mode="json",
            )
            for item in profiles_by_username.values()
        ]

        self._file_path.write_text(
            json.dumps(
                serialized,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
