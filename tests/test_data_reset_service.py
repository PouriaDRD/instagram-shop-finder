from __future__ import annotations

import json
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path

from app.storage.data_reset_service import (
    DataResetService,
)

FIXED_TIME = datetime(
    2026,
    9,
    1,
    12,
    30,
    45,
    123456,
    tzinfo=timezone.utc,
)


def write_json(
    path: Path,
    value: object,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def read_json(
    path: Path,
) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def make_service(
    tmp_path: Path,
) -> DataResetService:
    return DataResetService(
        profiles_file=(tmp_path / "profiles.json"),
        candidates_file=(tmp_path / "candidates.json"),
        latest_discovery_file=(tmp_path / "latest_discovery.json"),
        latest_validation_file=(tmp_path / "latest_validation.json"),
        backups_dir=(tmp_path / "backups"),
        now_provider=lambda: (FIXED_TIME),
    )


def populate_files(
    tmp_path: Path,
) -> None:
    write_json(
        tmp_path / "profiles.json",
        [{"username": "shop1"}],
    )

    write_json(
        tmp_path / "candidates.json",
        [{"username": "candidate1"}],
    )

    write_json(
        tmp_path / "latest_discovery.json",
        {
            "run_id": "run-1",
            "candidates": ["candidate1"],
        },
    )

    write_json(
        tmp_path / "latest_validation.json",
        {
            "run_id": "run-1",
            "results": ["candidate1"],
        },
    )


def test_reset_creates_backup_directory(
    tmp_path: Path,
) -> None:
    populate_files(tmp_path)

    service = make_service(tmp_path)

    result = service.reset()

    assert result.backup_directory.exists()

    assert result.backup_directory.parent == tmp_path / "backups"


def test_reset_backs_up_all_existing_data_files(
    tmp_path: Path,
) -> None:
    populate_files(tmp_path)

    service = make_service(tmp_path)

    result = service.reset()

    assert set(result.backed_up_files) == {
        "profiles.json",
        "candidates.json",
        "latest_discovery.json",
        "latest_validation.json",
    }

    for filename in result.backed_up_files:
        assert (result.backup_directory / filename).exists()


def test_backup_contains_original_profiles_data(
    tmp_path: Path,
) -> None:
    populate_files(tmp_path)

    service = make_service(tmp_path)

    result = service.reset()

    backup_profiles = read_json(result.backup_directory / "profiles.json")

    assert backup_profiles == [{"username": "shop1"}]


def test_backup_contains_original_candidates_data(
    tmp_path: Path,
) -> None:
    populate_files(tmp_path)

    service = make_service(tmp_path)

    result = service.reset()

    backup_candidates = read_json(result.backup_directory / "candidates.json")

    assert backup_candidates == [{"username": ("candidate1")}]


def test_profiles_and_candidates_are_reset_to_lists(
    tmp_path: Path,
) -> None:
    populate_files(tmp_path)

    service = make_service(tmp_path)

    service.reset()

    assert read_json(tmp_path / "profiles.json") == []

    assert read_json(tmp_path / "candidates.json") == []


def test_latest_snapshots_are_reset_to_objects(
    tmp_path: Path,
) -> None:
    populate_files(tmp_path)

    service = make_service(tmp_path)

    service.reset()

    assert read_json(tmp_path / "latest_discovery.json") == {}

    assert read_json(tmp_path / "latest_validation.json") == {}


def test_manifest_is_created(
    tmp_path: Path,
) -> None:
    populate_files(tmp_path)

    service = make_service(tmp_path)

    result = service.reset()

    manifest_file = result.backup_directory / "manifest.json"

    assert manifest_file.exists()

    manifest = read_json(manifest_file)

    assert manifest["purpose"] == "backup_before_data_reset"  # type: ignore

    assert set(manifest["backed_up_files"]) == {  # type: ignore
        "profiles.json",
        "candidates.json",
        "latest_discovery.json",
        "latest_validation.json",
    }


def test_backup_directory_is_not_deleted(
    tmp_path: Path,
) -> None:
    populate_files(tmp_path)

    old_backup = tmp_path / "backups" / "old_backup"

    old_backup.mkdir(parents=True)

    old_file = old_backup / "important.json"

    old_file.write_text(
        '{"safe": true}',
        encoding="utf-8",
    )

    service = make_service(tmp_path)

    service.reset()

    assert old_file.exists()


def test_missing_data_files_do_not_break_reset(
    tmp_path: Path,
) -> None:
    service = make_service(tmp_path)

    result = service.reset()

    assert result.backup_directory.exists()

    assert result.backed_up_files == ()

    assert read_json(tmp_path / "profiles.json") == []

    assert read_json(tmp_path / "candidates.json") == []

    assert read_json(tmp_path / "latest_discovery.json") == {}

    assert read_json(tmp_path / "latest_validation.json") == {}


def test_browser_profile_directory_is_untouched(
    tmp_path: Path,
) -> None:
    populate_files(tmp_path)

    browser_dir = tmp_path / "instagram-browser-profile"

    browser_dir.mkdir()

    browser_file = browser_dir / "Cookies"

    browser_file.write_text(
        "browser data",
        encoding="utf-8",
    )

    service = make_service(tmp_path)

    service.reset()

    assert browser_file.exists()

    assert browser_file.read_text(encoding="utf-8") == "browser data"
