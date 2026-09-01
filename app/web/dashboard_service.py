from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(
    frozen=True,
    slots=True,
)
class DashboardData:
    profiles: list[dict[str, Any]]
    candidates: list[dict[str, Any]]

    latest_discovery: dict[str, Any]
    latest_validation: dict[str, Any]

    stats: dict[str, int]


class DashboardService:
    """Read-only service for dashboard data."""

    def __init__(
        self,
        *,
        profiles_file: Path,
        candidates_file: Path,
        latest_discovery_file: Path,
        latest_validation_file: Path,
    ) -> None:
        self._profiles_file = profiles_file
        self._candidates_file = candidates_file
        self._latest_discovery_file = latest_discovery_file
        self._latest_validation_file = latest_validation_file

    @staticmethod
    def _read_json(
        path: Path,
        *,
        default: Any,
    ) -> Any:
        if not path.exists():
            return default

        raw = path.read_text(encoding="utf-8").strip()

        if not raw:
            return default

        try:
            return json.loads(raw)

        except json.JSONDecodeError:
            return default

    def get_profiles(
        self,
    ) -> list[dict[str, Any]]:
        data = self._read_json(
            self._profiles_file,
            default=[],
        )

        if not isinstance(
            data,
            list,
        ):
            return []

        return [
            item
            for item in data
            if isinstance(
                item,
                dict,
            )
        ]

    def get_candidates(
        self,
    ) -> list[dict[str, Any]]:
        data = self._read_json(
            self._candidates_file,
            default=[],
        )

        if not isinstance(
            data,
            list,
        ):
            return []

        return [
            item
            for item in data
            if isinstance(
                item,
                dict,
            )
        ]

    def get_latest_discovery(
        self,
    ) -> dict[str, Any]:
        data = self._read_json(
            self._latest_discovery_file,
            default={},
        )

        if not isinstance(
            data,
            dict,
        ):
            return {}

        return data

    def get_latest_validation(
        self,
    ) -> dict[str, Any]:
        data = self._read_json(
            self._latest_validation_file,
            default={},
        )

        if not isinstance(
            data,
            dict,
        ):
            return {}

        return data

    @staticmethod
    def _safe_list(
        value: Any,
    ) -> list[Any]:
        if isinstance(
            value,
            list,
        ):
            return value

        return []

    @staticmethod
    def _safe_dict(
        value: Any,
    ) -> dict[str, Any]:
        if isinstance(
            value,
            dict,
        ):
            return value

        return {}

    def get_dashboard_data(
        self,
    ) -> DashboardData:
        profiles = self.get_profiles()

        candidates = self.get_candidates()

        latest_discovery = self.get_latest_discovery()

        latest_validation = self.get_latest_validation()

        discovery_candidates = self._safe_list(latest_discovery.get("candidates"))

        validation_results = self._safe_list(latest_validation.get("results"))

        validation_summary = self._safe_dict(latest_validation.get("summary"))

        stats = {
            "profiles": len(profiles),
            "candidates": len(candidates),
            "latest_discovered": len(discovery_candidates),
            "latest_processed": len(validation_results),
            "matched": int(
                validation_summary.get(
                    "matched",
                    0,
                )
                or 0
            ),
            "rejected": int(
                validation_summary.get(
                    "rejected",
                    0,
                )
                or 0
            ),
            "incomplete": int(
                validation_summary.get(
                    "incomplete",
                    0,
                )
                or 0
            ),
            "fetch_failed": int(
                validation_summary.get(
                    "fetch_failed",
                    0,
                )
                or 0
            ),
            "already_saved": int(
                validation_summary.get(
                    "already_saved",
                    0,
                )
                or 0
            ),
            "rate_limited": int(
                validation_summary.get(
                    "rate_limited",
                    0,
                )
                or 0
            ),
        }

        return DashboardData(
            profiles=profiles,
            candidates=candidates,
            latest_discovery=(latest_discovery),
            latest_validation=(latest_validation),
            stats=stats,
        )
