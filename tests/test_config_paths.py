from app.config import (
    CANDIDATES_FILE,
    DATA_DIR,
    LATEST_DISCOVERY_FILE,
    LATEST_VALIDATION_FILE,
    PROFILES_FILE,
)


def test_permanent_storage_paths() -> None:
    assert PROFILES_FILE == DATA_DIR / "profiles.json"

    assert CANDIDATES_FILE == DATA_DIR / "candidates.json"


def test_latest_snapshot_paths() -> None:
    assert LATEST_DISCOVERY_FILE == DATA_DIR / "latest_discovery.json"

    assert LATEST_VALIDATION_FILE == DATA_DIR / "latest_validation.json"


def test_snapshot_files_are_separate_from_permanent_files() -> None:
    assert LATEST_DISCOVERY_FILE != CANDIDATES_FILE

    assert LATEST_VALIDATION_FILE != PROFILES_FILE
