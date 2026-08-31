from app.discovery.base import (
    DiscoverySource,
)
from app.discovery.multi_source import (
    MultiSourceDiscoverySource,
)


class FakeSource(DiscoverySource):
    def __init__(
        self,
        results,
    ):
        self.results = list(results)
        self.calls = []

    def discover(
        self,
        *,
        query: str,
        limit: int,
    ):
        self.calls.append(
            (
                query,
                limit,
            )
        )

        return self.results[:limit]


class FailingSource(DiscoverySource):
    def __init__(self):
        self.called = False

    def discover(
        self,
        *,
        query: str,
        limit: int,
    ):
        self.called = True

        raise RuntimeError("source failed")


def test_all_sources_are_attempted():
    first = FakeSource(
        [
            "a",
            "b",
            "c",
            "d",
        ]
    )

    second = FakeSource(
        [
            "e",
            "f",
            "g",
        ]
    )

    source = MultiSourceDiscoverySource(
        sources=(
            first,
            second,
        )
    )

    source.discover(
        query="test",
        limit=3,
    )

    assert len(first.calls) == 1
    assert len(second.calls) == 1


def test_results_are_round_robin():
    first = FakeSource(
        [
            "a",
            "b",
            "c",
        ]
    )

    second = FakeSource(
        [
            "x",
            "y",
            "z",
        ]
    )

    source = MultiSourceDiscoverySource(
        sources=(
            first,
            second,
        )
    )

    result = source.discover(
        query="test",
        limit=6,
    )

    assert result == [
        "a",
        "x",
        "b",
        "y",
        "c",
        "z",
    ]


def test_duplicates_are_removed_globally():
    first = FakeSource(
        [
            "shop_a",
            "shop_b",
        ]
    )

    second = FakeSource(
        [
            "SHOP_A",
            "@shop_c",
        ]
    )

    source = MultiSourceDiscoverySource(
        sources=(
            first,
            second,
        )
    )

    result = source.discover(
        query="test",
        limit=10,
    )

    assert result == [
        "shop_a",
        "shop_b",
        "shop_c",
    ]


def test_source_failure_does_not_stop_others():
    failing = FailingSource()

    working = FakeSource(
        [
            "shop_a",
            "shop_b",
        ]
    )

    source = MultiSourceDiscoverySource(
        sources=(
            failing,
            working,
        )
    )

    result = source.discover(
        query="test",
        limit=10,
    )

    assert failing.called is True

    assert result == [
        "shop_a",
        "shop_b",
    ]


def test_empty_source_does_not_stop_others():
    empty = FakeSource([])

    working = FakeSource(
        [
            "shop_a",
        ]
    )

    source = MultiSourceDiscoverySource(
        sources=(
            empty,
            working,
        )
    )

    result = source.discover(
        query="test",
        limit=10,
    )

    assert result == [
        "shop_a",
    ]


def test_username_normalization():
    source = FakeSource(
        [
            " @Shop.Name ",
        ]
    )

    combined = MultiSourceDiscoverySource(sources=(source,))

    result = combined.discover(
        query="test",
        limit=10,
    )

    assert result == [
        "shop.name",
    ]
