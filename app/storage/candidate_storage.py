from __future__ import annotations

from datetime import datetime, timezone

from app.models.candidate import (
    CandidateCategoryConfidence,
    CandidateDiscoveryEvidence,
    CandidateRetryContext,
    CandidateStatus,
    InstagramCandidate,
)
from app.models.profile import (
    ProfileCategory,
)
from app.storage.base_storage import (
    JsonFileStorage,
)


class CandidateStorage(JsonFileStorage[InstagramCandidate]):
    MAX_INCOMPLETE_RETRIES = 3

    PROCESSABLE_STATUSES: frozenset[CandidateStatus] = frozenset(
        {
            CandidateStatus.NEW,
            CandidateStatus.FETCH_FAILED,
            CandidateStatus.RATE_LIMITED,
            CandidateStatus.INCOMPLETE,
        }
    )

    RETRY_CHAIN_STATUSES: frozenset[CandidateStatus] = frozenset(
        {
            CandidateStatus.FETCH_FAILED,
            CandidateStatus.INCOMPLETE,
        }
    )

    TERMINAL_STATUSES: frozenset[CandidateStatus] = frozenset(
        {
            CandidateStatus.REJECTED,
            CandidateStatus.MATCHED,
            CandidateStatus.ALREADY_SAVED,
        }
    )

    def get_all(
        self,
    ) -> list[InstagramCandidate]:
        return [InstagramCandidate.model_validate(item) for item in self._read_raw()]

    def get_by_username(
        self,
        username: str,
    ) -> InstagramCandidate | None:
        normalized = self._normalize_username(username)

        for candidate in self.get_all():
            if candidate.username.lower() == normalized:
                return candidate

        return None

    def save(
        self,
        candidate: InstagramCandidate,
    ) -> None:
        raw_items = self._read_raw()

        candidates_by_username = {
            str(
                item.get(
                    "username",
                    "",
                )
            ).lower(): item
            for item in raw_items
        }

        candidates_by_username[candidate.username.lower()] = candidate.model_dump(
            mode="json",
        )

        self._write_raw(list(candidates_by_username.values()))

    @staticmethod
    def _has_same_evidence(
        candidate: InstagramCandidate,
        *,
        run_id: str,
        category: ProfileCategory | None,
        query: str,
        source: str,
    ) -> bool:
        return any(
            (
                evidence.run_id == run_id
                and evidence.category == category
                and evidence.query == query
                and evidence.source == source
            )
            for evidence in candidate.discovery_evidence
        )

    @staticmethod
    def _has_run_evidence(
        candidate: InstagramCandidate,
        *,
        run_id: str,
    ) -> bool:
        return any(
            evidence.run_id == run_id for evidence in candidate.discovery_evidence
        )

    def upsert_discovered(
        self,
        *,
        username: str,
        query: str,
        requested_category: ProfileCategory | None,
        source: str,
        run_id: str,
    ) -> bool:
        normalized = self._normalize_username(username)

        if not normalized:
            return False

        now = datetime.now(timezone.utc)

        existing = self.get_by_username(normalized)

        if existing is not None:
            if query not in existing.queries:
                existing.queries.append(query)

            if source not in existing.sources:
                existing.sources.append(source)

            if (
                requested_category is not None
                and requested_category not in existing.requested_categories
            ):
                existing.requested_categories.append(requested_category)

            if not self._has_same_evidence(
                existing,
                run_id=run_id,
                category=requested_category,
                query=query,
                source=source,
            ):
                existing.discovery_evidence.append(
                    CandidateDiscoveryEvidence(
                        run_id=run_id,
                        category=requested_category,
                        query=query,
                        source=source,
                        discovered_at=now,
                    )
                )

            existing.last_discovered_at = now

            # The candidate was rediscovered in the current run.
            #
            # Current-run evidence is now authoritative, so an older
            # retry origin is no longer needed.
            existing.retry_context = None

            self.save(existing)

            return False

        candidate = InstagramCandidate(
            username=normalized,
            profile_url=("https://www.instagram.com/" f"{normalized}/"),
            status=CandidateStatus.NEW,
            queries=[query],
            sources=[source],
            requested_categories=(
                [requested_category] if requested_category is not None else []
            ),
            discovery_evidence=[
                CandidateDiscoveryEvidence(
                    run_id=run_id,
                    category=(requested_category),
                    query=query,
                    source=source,
                    discovered_at=now,
                )
            ],
            retry_context=None,
            first_discovered_at=now,
            last_discovered_at=now,
        )

        self.save(candidate)

        return True

    def _update_retry_context(
        self,
        candidate: InstagramCandidate,
        *,
        status: CandidateStatus,
        current_run_id: str | None,
    ) -> None:
        if status in self.TERMINAL_STATUSES:
            candidate.retry_context = None
            return

        if status not in self.RETRY_CHAIN_STATUSES:
            return

        # If this candidate was actually discovered during this run,
        # then this run becomes the retry origin.
        if current_run_id is not None and self._has_run_evidence(
            candidate,
            run_id=(current_run_id),
        ):
            previous_retry_count = 0

            if (
                candidate.retry_context is not None
                and candidate.retry_context.origin_run_id == current_run_id
            ):
                previous_retry_count = candidate.retry_context.retry_count

            candidate.retry_context = CandidateRetryContext(
                origin_run_id=(current_run_id),
                origin_status=status,
                started_at=(
                    candidate.retry_context.started_at
                    if (
                        candidate.retry_context is not None
                        and candidate.retry_context.origin_run_id == current_run_id
                    )
                    else datetime.now(timezone.utc)
                ),
                retry_count=(previous_retry_count + 1),
            )

            return

        # No current-run discovery evidence exists.
        #
        # This means the candidate probably entered the queue from
        # a previous incomplete/fetch_failed state.
        #
        # Preserve that original retry context.
        if candidate.retry_context is not None:
            candidate.retry_context.retry_count += 1

    def update_status(
        self,
        username: str,
        *,
        status: CandidateStatus,
        current_run_id: str | None = None,
        followers_count: int | None = None,
        detected_category: ProfileCategory | None = None,
        resolved_category: ProfileCategory | None = None,
        category_confidence: CandidateCategoryConfidence | None = None,
        is_shop: bool | None = None,
        shop_score: float | None = None,
        rejection_reason: str | None = None,
        error: str | None = None,
        incomplete_reason: str | None = None,
    ) -> None:
        candidate = self.get_by_username(username)

        if candidate is None:
            return

        candidate.status = status

        candidate.last_checked_at = datetime.now(timezone.utc)

        candidate.check_attempts += 1

        if status == CandidateStatus.INCOMPLETE:
            candidate.incomplete_attempts += 1

        if followers_count is not None:
            candidate.followers_count = followers_count

        if detected_category is not None:
            candidate.detected_category = detected_category

        if resolved_category is not None:
            candidate.resolved_category = resolved_category

        if category_confidence is not None:
            candidate.category_confidence = category_confidence

        if is_shop is not None:
            candidate.is_shop = is_shop

        if shop_score is not None:
            candidate.shop_score = shop_score

        candidate.rejection_reason = rejection_reason

        candidate.last_error = error

        candidate.incomplete_reason = incomplete_reason

        self._update_retry_context(
            candidate,
            status=status,
            current_run_id=(current_run_id),
        )

        self.save(candidate)

    def get_processable_usernames(
        self,
        *,
        requested_category: ProfileCategory | None = None,
    ) -> list[str]:
        usernames: list[str] = []

        for candidate in self.get_all():
            if candidate.status not in self.PROCESSABLE_STATUSES:
                continue

            if (
                candidate.status == CandidateStatus.INCOMPLETE
                and candidate.incomplete_attempts >= self.MAX_INCOMPLETE_RETRIES
            ):
                continue

            # Queue scoping only.
            #
            # requested_categories is NOT category evidence.
            if requested_category is not None:
                if (
                    candidate.requested_categories
                    and requested_category not in candidate.requested_categories
                ):
                    continue

            usernames.append(candidate.username)

        return usernames
