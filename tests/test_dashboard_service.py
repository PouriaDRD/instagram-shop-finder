from __future__ import annotations

import json
from pathlib import Path

from app.web.dashboard_service import (
    DashboardService,
)


def write_json(
    path: Path,
    data: object,
) -> None:
    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def make_service(
    tmp_path: Path,
) -> DashboardService:
    return DashboardService(
        profiles_file=(tmp_path / "profiles.json"),
        candidates_file=(tmp_path / "candidates.json"),
        latest_discovery_file=(tmp_path / "latest_discovery.json"),
        latest_validation_file=(tmp_path / "latest_validation.json"),
    )


def test_empty_files_return_empty_dashboard(
    tmp_path: Path,
) -> None:
    service = make_service(tmp_path)

    data = service.get_dashboard_data()

    assert data.profiles == []
    assert data.candidates == []

    assert data.latest_discovery == {}

    assert data.latest_validation == {}

    assert data.stats["profiles"] == 0

    assert data.stats["candidates"] == 0


def test_dashboard_counts_profiles_and_candidates(
    tmp_path: Path,
) -> None:
    write_json(
        tmp_path / "profiles.json",
        [
            {"username": "a"},
            {"username": "b"},
        ],
    )

    write_json(
        tmp_path / "candidates.json",
        [
            {"username": "a"},
            {"username": "b"},
            {"username": "c"},
        ],
    )

    service = make_service(tmp_path)

    data = service.get_dashboard_data()

    assert data.stats["profiles"] == 2

    assert data.stats["candidates"] == 3


def test_dashboard_reads_latest_discovery(
    tmp_path: Path,
) -> None:
    write_json(
        tmp_path / "latest_discovery.json",
        {
            "candidates": [
                {"username": "one"},
                {"username": "two"},
            ]
        },
    )

    service = make_service(tmp_path)

    data = service.get_dashboard_data()

    assert data.stats["latest_discovered"] == 2


def test_dashboard_reads_validation_summary(
    tmp_path: Path,
) -> None:
    write_json(
        tmp_path / "latest_validation.json",
        {
            "summary": {
                "matched": 5,
                "rejected": 7,
                "incomplete": 2,
                "fetch_failed": 1,
                "already_saved": 3,
                "rate_limited": 1,
            },
            "results": [
                {"username": "a"},
                {"username": "b"},
            ],
        },
    )

    service = make_service(tmp_path)

    data = service.get_dashboard_data()

    assert data.stats["latest_processed"] == 2

    assert data.stats["matched"] == 5

    assert data.stats["rejected"] == 7

    assert data.stats["incomplete"] == 2

    assert data.stats["fetch_failed"] == 1


def test_invalid_json_does_not_crash_dashboard(
    tmp_path: Path,
) -> None:
    profiles_file = tmp_path / "profiles.json"

    profiles_file.write_text(
        "{broken json",
        encoding="utf-8",
    )

    service = make_service(tmp_path)

    data = service.get_dashboard_data()

    assert data.profiles == []

    assert data.stats["profiles"] == 0
