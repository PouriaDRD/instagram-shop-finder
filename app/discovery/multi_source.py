from __future__ import annotations

import math

from app.discovery.base import (
    DiscoverySource,
)


class MultiSourceDiscoverySource(DiscoverySource):
    """
    Merge candidate usernames from multiple independent sources.

    Important behavior:
    - every source gets a chance to run
    - one prolific source cannot starve the others
    - usernames are normalized globally
    - duplicates are removed globally
    - source failures do not stop discovery
    """

    def __init__(
        self,
        sources: tuple[DiscoverySource, ...],
    ) -> None:
        if not sources:
            raise ValueError("At least one discovery source is required.")

        self._sources = sources

    def discover(
        self,
        *,
        query: str,
        limit: int,
    ) -> list[str]:
        if limit <= 0:
            return []

        results: list[str] = []
        seen: set[str] = set()

        source_count = len(self._sources)

        # Give every source a useful quota.
        #
        # Example:
        # limit=20, sources=4
        # each source may return up to 10.
        #
        # We collect globally until the real limit is reached.
        fair_share = math.ceil(limit / source_count)

        per_source_limit = min(
            limit,
            max(
                10,
                fair_share,
            ),
        )

        source_batches: list[list[str]] = []

        for source in self._sources:
            try:
                candidates = source.discover(
                    query=query,
                    limit=per_source_limit,
                )

            except Exception:
                candidates = []

            normalized_batch: list[str] = []

            batch_seen: set[str] = set()

            for username in candidates:
                normalized = str(username).strip().lstrip("@").lower()

                if not normalized:
                    continue

                if normalized in batch_seen:
                    continue

                batch_seen.add(normalized)

                normalized_batch.append(normalized)

            source_batches.append(normalized_batch)

        # Round-robin merge:
        #
        # source A item 1
        # source B item 1
        # source C item 1
        # source A item 2
        # ...
        #
        # This prevents the first source from dominating results.
        index = 0

        while len(results) < limit:
            added_this_round = False

            for batch in source_batches:
                if index >= len(batch):
                    continue

                username = batch[index]

                if username in seen:
                    continue

                seen.add(username)

                results.append(username)

                added_this_round = True

                if len(results) >= limit:
                    break

            if not added_this_round:
                # There may still be duplicates at this index,
                # so determine whether later items exist.
                has_later_items = any(
                    len(batch) > index + 1 for batch in source_batches
                )

                if not has_later_items:
                    break

            index += 1

        return results
