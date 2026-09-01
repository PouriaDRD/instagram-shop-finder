from __future__ import annotations

import json
from pathlib import Path

from app.models.profile import ProfileCategory
from app.storage.run_snapshot_storage import RunSnapshotStorage


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def make_storage(
    tmp_path: Path,
) -> RunSnapshotStorage:
    return RunSnapshotStorage(
        discovery_file=(tmp_path / "latest_discovery.json"),
        validation_file=(tmp_path / "latest_validation.json"),
    )


def start_test_run(
    storage: RunSnapshotStorage,
    *,
    run_id: str = "run-1",
) -> None:
    storage.start_run(
        run_id=run_id,
        category=ProfileCategory.TOYS,
        min_followers=10_000,
        max_followers=None,
        min_shop_score=0.22,
        target_results=5,
        additional_query=None,
        max_candidates=150,
    )


def test_start_run_creates_both_snapshot_files(
    tmp_path: Path,
) -> None:
    storage = make_storage(tmp_path)

    start_test_run(storage)

    assert storage.discovery_file.exists()
    assert storage.validation_file.exists()


def test_start_run_initializes_discovery_snapshot(
    tmp_path: Path,
) -> None:
    storage = make_storage(tmp_path)

    start_test_run(storage)

    data = read_json(storage.discovery_file)

    assert data["run_id"] == "run-1"
    assert data["category"] == "toys"
    assert data["candidate_count"] == 0
    assert data["candidates"] == []

    assert data["filters"]["min_followers"] == 10_000

    assert data["filters"]["min_shop_score"] == 0.22

    assert data["filters"]["target_results"] == 5


def test_start_run_initializes_validation_snapshot(
    tmp_path: Path,
) -> None:
    storage = make_storage(tmp_path)

    start_test_run(storage)

    data = read_json(storage.validation_file)

    assert data["run_id"] == "run-1"
    assert data["category"] == "toys"
    assert data["completed"] is False
    assert data["completed_at"] is None
    assert data["stop_reason"] is None
    assert data["results"] == []

    assert data["summary"] == {
        "processed": 0,
        "matched": 0,
        "rejected": 0,
        "incomplete": 0,
        "fetch_failed": 0,
        "rate_limited": 0,
        "already_saved": 0,
        "non_iranian": 0,
    }


def test_new_run_overwrites_previous_discovery_snapshot(
    tmp_path: Path,
) -> None:
    storage = make_storage(tmp_path)

    start_test_run(
        storage,
        run_id="run-1",
    )

    storage.record_discovery_candidate(
        username="oldshop",
        profile_url=("https://www.instagram.com/" "oldshop/"),
        query="old query",
        source="OldSource",
        requested_category=(ProfileCategory.TOYS),
        is_new_candidate=True,
    )

    before = read_json(storage.discovery_file)

    assert before["candidate_count"] == 1

    start_test_run(
        storage,
        run_id="run-2",
    )

    after = read_json(storage.discovery_file)

    assert after["run_id"] == "run-2"
    assert after["candidate_count"] == 0
    assert after["candidates"] == []

    usernames = [item["username"] for item in after["candidates"]]

    assert "oldshop" not in usernames


def test_new_run_overwrites_previous_validation_snapshot(
    tmp_path: Path,
) -> None:
    storage = make_storage(tmp_path)

    start_test_run(
        storage,
        run_id="run-1",
    )

    storage.record_validation(
        username="oldshop",
        profile_url=("https://www.instagram.com/" "oldshop/"),
        origin="current_discovery",
        result="matched",
        followers_count=50_000,
        detected_category=(ProfileCategory.TOYS),
        resolved_category=(ProfileCategory.TOYS),
        category_confidence="confirmed",
        evidence_source="classifier",
        shop_score=0.80,
        is_shop=True,
    )

    before = read_json(storage.validation_file)

    assert before["summary"]["matched"] == 1
    assert len(before["results"]) == 1

    start_test_run(
        storage,
        run_id="run-2",
    )

    after = read_json(storage.validation_file)

    assert after["run_id"] == "run-2"
    assert after["results"] == []
    assert after["summary"]["processed"] == 0
    assert after["summary"]["matched"] == 0


def test_record_discovery_candidate(
    tmp_path: Path,
) -> None:
    storage = make_storage(tmp_path)

    start_test_run(storage)

    storage.record_discovery_candidate(
        username="toyshop",
        profile_url=("https://www.instagram.com/" "toyshop/"),
        query=("site:instagram.com " '"فروشگاه اسباب بازی"'),
        source=("MultiSourceDiscoverySource"),
        requested_category=(ProfileCategory.TOYS),
        is_new_candidate=True,
    )

    data = read_json(storage.discovery_file)

    assert data["candidate_count"] == 1
    assert len(data["candidates"]) == 1

    candidate = data["candidates"][0]

    assert candidate["username"] == "toyshop"

    assert candidate["profile_url"] == ("https://www.instagram.com/" "toyshop/")

    assert candidate["requested_category"] == "toys"

    assert candidate["source"] == "MultiSourceDiscoverySource"

    assert candidate["is_new_candidate"] is True

    assert candidate["discovered_at"] is not None


def test_record_multiple_discovery_candidates(
    tmp_path: Path,
) -> None:
    storage = make_storage(tmp_path)

    start_test_run(storage)

    for index in range(3):
        username = f"shop{index}"

        storage.record_discovery_candidate(
            username=username,
            profile_url=("https://www.instagram.com/" f"{username}/"),
            query="test query",
            source="TestSource",
            requested_category=(ProfileCategory.TOYS),
            is_new_candidate=True,
        )

    data = read_json(storage.discovery_file)

    assert data["candidate_count"] == 3
    assert len(data["candidates"]) == 3


def test_record_matched_validation(
    tmp_path: Path,
) -> None:
    storage = make_storage(tmp_path)

    start_test_run(storage)

    storage.record_validation(
        username="matchedshop",
        profile_url=("https://www.instagram.com/" "matchedshop/"),
        origin="current_discovery",
        result="matched",
        followers_count=25_000,
        detected_category=(ProfileCategory.TOYS),
        resolved_category=(ProfileCategory.TOYS),
        category_confidence="confirmed",
        evidence_source="classifier",
        shop_score=0.80,
        is_shop=True,
    )

    data = read_json(storage.validation_file)

    assert data["summary"]["processed"] == 1
    assert data["summary"]["matched"] == 1
    assert data["summary"]["rejected"] == 0

    result = data["results"][0]

    assert result["username"] == "matchedshop"

    assert result["result"] == "matched"

    assert result["origin"] == "current_discovery"

    assert result["detected_category"] == "toys"

    assert result["resolved_category"] == "toys"

    assert result["category_confidence"] == "confirmed"

    assert result["evidence_source"] == "classifier"

    assert result["shop_score"] == 0.80
    assert result["is_shop"] is True
    assert result["reason"] is None


def test_record_rejected_validation(
    tmp_path: Path,
) -> None:
    storage = make_storage(tmp_path)

    start_test_run(storage)

    storage.record_validation(
        username="smallshop",
        profile_url=("https://www.instagram.com/" "smallshop/"),
        origin="current_discovery",
        result="rejected",
        followers_count=5_000,
        detected_category=(ProfileCategory.TOYS),
        resolved_category=(ProfileCategory.TOYS),
        category_confidence="confirmed",
        evidence_source="classifier",
        shop_score=0.90,
        is_shop=True,
        reason=("followers below minimum"),
    )

    data = read_json(storage.validation_file)

    assert data["summary"]["processed"] == 1
    assert data["summary"]["rejected"] == 1

    result = data["results"][0]

    assert result["result"] == "rejected"

    assert result["reason"] == "followers below minimum"


def test_retry_pending_origin_is_saved(
    tmp_path: Path,
) -> None:
    storage = make_storage(tmp_path)

    start_test_run(storage)

    storage.record_validation(
        username="retryshop",
        profile_url=("https://www.instagram.com/" "retryshop/"),
        origin="retry_pending",
        result="matched",
        followers_count=30_000,
        detected_category=(ProfileCategory.UNKNOWN),
        resolved_category=(ProfileCategory.TOYS),
        category_confidence="probable",
        evidence_source="retry_origin",
        shop_score=0.85,
        is_shop=True,
    )

    data = read_json(storage.validation_file)

    result = data["results"][0]

    assert result["origin"] == "retry_pending"

    assert result["evidence_source"] == "retry_origin"

    assert result["detected_category"] == "unknown"

    assert result["resolved_category"] == "toys"


def test_all_validation_results_update_correct_counters(
    tmp_path: Path,
) -> None:
    storage = make_storage(tmp_path)

    start_test_run(storage)

    statuses = (
        "matched",
        "rejected",
        "incomplete",
        "fetch_failed",
        "rate_limited",
        "already_saved",
        "non_iranian",
    )

    for index, status in enumerate(
        statuses,
        start=1,
    ):
        username = f"shop{index}"

        storage.record_validation(
            username=username,
            profile_url=("https://www.instagram.com/" f"{username}/"),
            origin="current_discovery",
            result=status,
        )

    data = read_json(storage.validation_file)

    summary = data["summary"]

    assert summary["processed"] == len(statuses)

    for status in statuses:
        assert summary[status] == 1

    assert len(data["results"]) == len(statuses)


def test_finish_run_marks_snapshot_completed(
    tmp_path: Path,
) -> None:
    storage = make_storage(tmp_path)

    start_test_run(storage)

    storage.finish_run(
        completed=True,
    )

    data = read_json(storage.validation_file)

    assert data["completed"] is True

    assert data["completed_at"] is not None

    assert data["stop_reason"] is None


def test_finish_run_can_mark_cancelled_run(
    tmp_path: Path,
) -> None:
    storage = make_storage(tmp_path)

    start_test_run(storage)

    storage.finish_run(
        completed=False,
        stop_reason=("cancelled_before_instagram_check"),
    )

    data = read_json(storage.validation_file)

    assert data["completed"] is False

    assert data["stop_reason"] == ("cancelled_before_instagram_check")


def test_finish_run_can_mark_rate_limit_stop(
    tmp_path: Path,
) -> None:
    storage = make_storage(tmp_path)

    start_test_run(storage)

    storage.finish_run(
        completed=False,
        stop_reason=("rate_limit_safety_stop"),
    )

    data = read_json(storage.validation_file)

    assert data["completed"] is False

    assert data["stop_reason"] == "rate_limit_safety_stop"
