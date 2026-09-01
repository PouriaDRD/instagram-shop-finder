from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.profile import ProfileCategory


class RunSnapshotStorage:
    """Temporary storage for the latest automatic discovery run.

    Permanent application storage:
        - candidates.json
        - profiles.json

    Temporary latest-run snapshots:
        - latest_discovery.json
        - latest_validation.json

    Every new automatic discovery run overwrites both latest files.
    """

    _VALIDATION_SUMMARY_KEYS: tuple[str, ...] = (
        "processed",
        "matched",
        "rejected",
        "incomplete",
        "fetch_failed",
        "rate_limited",
        "already_saved",
        "non_iranian",
    )

    def __init__(
        self,
        *,
        discovery_file: Path,
        validation_file: Path,
    ) -> None:
        self._discovery_file = discovery_file
        self._validation_file = validation_file

        self._discovery_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._validation_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    @property
    def discovery_file(self) -> Path:
        return self._discovery_file

    @property
    def validation_file(self) -> Path:
        return self._validation_file

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _category_value(
        category: ProfileCategory | None,
    ) -> str | None:
        if category is None:
            return None

        return category.value

    @staticmethod
    def _write_json(
        path: Path,
        data: dict[str, Any],
    ) -> None:
        path.write_text(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _read_json(
        path: Path,
    ) -> dict[str, Any]:
        if not path.exists():
            return {}

        raw_text = path.read_text(encoding="utf-8").strip()

        if not raw_text:
            return {}

        data = json.loads(raw_text)

        if not isinstance(
            data,
            dict,
        ):
            raise ValueError(f"Snapshot file must contain " f"a JSON object: {path}")

        return data

    def start_run(
        self,
        *,
        run_id: str,
        category: ProfileCategory | None,
        min_followers: int | None,
        max_followers: int | None,
        min_shop_score: float,
        target_results: int,
        additional_query: str | None,
        max_candidates: int,
    ) -> None:
        """Overwrite snapshots from the previous run."""

        started_at = self._now()

        common_filters = {
            "min_followers": min_followers,
            "max_followers": max_followers,
            "min_shop_score": min_shop_score,
            "target_results": target_results,
            "additional_query": additional_query,
            "max_candidates": max_candidates,
        }

        discovery_data: dict[str, Any] = {
            "run_id": run_id,
            "started_at": started_at,
            "category": self._category_value(category),
            "filters": common_filters,
            "candidate_count": 0,
            "candidates": [],
        }

        validation_data: dict[str, Any] = {
            "run_id": run_id,
            "started_at": started_at,
            "completed_at": None,
            "completed": False,
            "stop_reason": None,
            "category": self._category_value(category),
            "filters": common_filters,
            "summary": {key: 0 for key in self._VALIDATION_SUMMARY_KEYS},
            "results": [],
        }

        self._write_json(
            self._discovery_file,
            discovery_data,
        )

        self._write_json(
            self._validation_file,
            validation_data,
        )

    def record_discovery_candidate(
        self,
        *,
        username: str,
        profile_url: str,
        query: str,
        source: str,
        requested_category: ProfileCategory | None,
        is_new_candidate: bool,
    ) -> None:
        data = self._read_json(self._discovery_file)

        if not data:
            raise RuntimeError("Discovery snapshot has not been started.")

        candidates = data.get("candidates")

        if not isinstance(
            candidates,
            list,
        ):
            raise ValueError("latest_discovery.json " "'candidates' must be a list.")

        candidates.append(
            {
                "username": username,
                "profile_url": profile_url,
                "query": query,
                "source": source,
                "requested_category": (self._category_value(requested_category)),
                "is_new_candidate": (is_new_candidate),
                "discovered_at": self._now(),
            }
        )

        data["candidate_count"] = len(candidates)

        self._write_json(
            self._discovery_file,
            data,
        )

    def record_validation(
        self,
        *,
        username: str,
        profile_url: str,
        origin: str,
        result: str,
        followers_count: int | None = None,
        detected_category: ProfileCategory | None = None,
        resolved_category: ProfileCategory | None = None,
        category_confidence: str | None = None,
        evidence_source: str | None = None,
        shop_score: float | None = None,
        is_shop: bool | None = None,
        reason: str | None = None,
    ) -> None:
        data = self._read_json(self._validation_file)

        if not data:
            raise RuntimeError("Validation snapshot has not been started.")

        results = data.get("results")

        if not isinstance(
            results,
            list,
        ):
            raise ValueError("latest_validation.json " "'results' must be a list.")

        results.append(
            {
                "username": username,
                "profile_url": profile_url,
                "origin": origin,
                "result": result,
                "followers_count": (followers_count),
                "detected_category": (self._category_value(detected_category)),
                "resolved_category": (self._category_value(resolved_category)),
                "category_confidence": (category_confidence),
                "evidence_source": (evidence_source),
                "shop_score": shop_score,
                "is_shop": is_shop,
                "reason": reason,
                "checked_at": self._now(),
            }
        )

        summary = data.get("summary")

        if not isinstance(
            summary,
            dict,
        ):
            raise ValueError("latest_validation.json " "'summary' must be an object.")

        summary["processed"] = (
            int(
                summary.get(
                    "processed",
                    0,
                )
            )
            + 1
        )

        result_to_summary_key = {
            "matched": "matched",
            "rejected": "rejected",
            "incomplete": "incomplete",
            "fetch_failed": "fetch_failed",
            "rate_limited": "rate_limited",
            "already_saved": "already_saved",
            "non_iranian": "non_iranian",
        }

        summary_key = result_to_summary_key.get(result)

        if summary_key is not None:
            summary[summary_key] = (
                int(
                    summary.get(
                        summary_key,
                        0,
                    )
                )
                + 1
            )

        self._write_json(
            self._validation_file,
            data,
        )

    def finish_run(
        self,
        *,
        completed: bool = True,
        stop_reason: str | None = None,
    ) -> None:
        data = self._read_json(self._validation_file)

        if not data:
            return

        data["completed"] = completed
        data["completed_at"] = self._now()
        data["stop_reason"] = stop_reason

        self._write_json(
            self._validation_file,
            data,
        )
