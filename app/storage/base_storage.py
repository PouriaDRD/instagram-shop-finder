import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class JsonFileStorage(Generic[T]):
    """Generic base class providing atomic JSON array persistence and utility functions."""

    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        """Ensures target parent directories and valid initial JSON file exist."""
        self._file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if not self._file_path.exists():
            self._file_path.write_text(
                "[]",
                encoding="utf-8",
            )

    @staticmethod
    def _now() -> str:
        """Generates an ISO 8601 UTC timestamp string."""
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _normalize_username(username: str) -> str:
        """Strips '@' symbols and whitespace, returning a lowercased handle."""
        return username.strip().lstrip("@").lower()

    def _read_raw(self) -> list[dict[str, Any]]:
        """Reads and parses raw JSON array records from disk."""
        raw_text = self._file_path.read_text(encoding="utf-8").strip()

        if not raw_text:
            return []

        data = json.loads(raw_text)

        if not isinstance(data, list):
            raise ValueError(
                f"Storage file '{self._file_path}' must contain a JSON array."
            )

        return data

    def _write_raw(self, items: list[dict[str, Any]]) -> None:
        """Serializes raw dict records to disk with standard UTF-8 formatting."""
        self._file_path.write_text(
            json.dumps(
                items,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def count(self) -> int:
        """Returns total record count inside the storage file."""
        return len(self._read_raw())
