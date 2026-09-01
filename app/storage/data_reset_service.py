from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


@dataclass(
    frozen=True,
    slots=True,
)
class DataResetResult:
    backup_directory: Path

    backed_up_files: tuple[str, ...]

    cleared_files: tuple[str, ...]


class DataResetService:
    """Backup and clear application JSON data safely.

    Important:
    - Backup is created before any data file is modified.
    - Browser/session data is NOT touched.
    - Backup directories are NEVER cleared by this service.
    """

    def __init__(
        self,
        *,
        profiles_file: Path,
        candidates_file: Path,
        latest_discovery_file: Path,
        latest_validation_file: Path,
        backups_dir: Path,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._profiles_file = profiles_file

        self._candidates_file = candidates_file

        self._latest_discovery_file = latest_discovery_file

        self._latest_validation_file = latest_validation_file

        self._backups_dir = backups_dir

        self._now_provider = now_provider or self._default_now

    @staticmethod
    def _default_now() -> datetime:
        return datetime.now(timezone.utc)

    @property
    def data_files(
        self,
    ) -> tuple[Path, ...]:
        return (
            self._profiles_file,
            self._candidates_file,
            self._latest_discovery_file,
            self._latest_validation_file,
        )

    def _create_backup_directory(
        self,
    ) -> tuple[
        Path,
        datetime,
    ]:
        now = self._now_provider()

        timestamp = now.strftime("%Y%m%d_%H%M%S_%f")

        backup_directory = self._backups_dir / timestamp

        backup_directory.mkdir(
            parents=True,
            exist_ok=False,
        )

        return (
            backup_directory,
            now,
        )

    @staticmethod
    def _write_manifest(
        *,
        backup_directory: Path,
        created_at: datetime,
        backed_up_files: list[str],
    ) -> None:
        manifest = {
            "created_at": (created_at.isoformat()),
            "purpose": ("backup_before_data_reset"),
            "backed_up_files": (backed_up_files),
        }

        manifest_file = backup_directory / "manifest.json"

        manifest_file.write_text(
            json.dumps(
                manifest,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _clear_json_file(
        path: Path,
    ) -> None:
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if path.name in {
            "profiles.json",
            "candidates.json",
        }:
            empty_value: object = []
        else:
            empty_value = {}

        path.write_text(
            json.dumps(
                empty_value,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def backup(
        self,
    ) -> Path:
        (
            backup_directory,
            created_at,
        ) = self._create_backup_directory()

        backed_up_files: list[str] = []

        try:
            for source_file in self.data_files:
                if not (source_file.exists()):
                    continue

                destination = backup_directory / source_file.name

                shutil.copy2(
                    source_file,
                    destination,
                )

                backed_up_files.append(source_file.name)

            self._write_manifest(
                backup_directory=(backup_directory),
                created_at=created_at,
                backed_up_files=(backed_up_files),
            )

        except Exception:
            shutil.rmtree(
                backup_directory,
                ignore_errors=True,
            )

            raise

        return backup_directory

    def reset(
        self,
    ) -> DataResetResult:
        """Backup first and only then clear data."""

        backup_directory = self.backup()

        backed_up_files = tuple(
            path.name
            for path in self.data_files
            if (backup_directory / path.name).exists()
        )

        cleared_files: list[str] = []

        try:
            for data_file in self.data_files:
                self._clear_json_file(data_file)

                cleared_files.append(data_file.name)

        except Exception as exc:
            raise RuntimeError(
                "Backup was created successfully, "
                "but clearing application data failed. "
                f"Backup is available at: "
                f"{backup_directory}"
            ) from exc

        return DataResetResult(
            backup_directory=(backup_directory),
            backed_up_files=(backed_up_files),
            cleared_files=tuple(cleared_files),
        )
