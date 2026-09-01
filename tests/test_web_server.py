from __future__ import annotations

import json
from pathlib import Path

from app.web.dashboard_service import (
    DashboardService,
)
from app.web.server import (
    create_app,
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


def test_dashboard_route_returns_200(
    tmp_path: Path,
) -> None:
    write_json(
        tmp_path / "profiles.json",
        [],
    )

    write_json(
        tmp_path / "candidates.json",
        [],
    )

    write_json(
        tmp_path / "latest_discovery.json",
        {},
    )

    write_json(
        tmp_path / "latest_validation.json",
        {},
    )

    service = make_service(tmp_path)

    app = create_app(service)

    app.config["TESTING"] = True

    client = app.test_client()

    response = client.get("/")

    assert response.status_code == 200

    html = response.data.decode("utf-8")

    assert "پنل جستجوی فروشگاه‌های اینستاگرامی" in html


def test_dashboard_displays_profile(
    tmp_path: Path,
) -> None:
    write_json(
        tmp_path / "profiles.json",
        [
            {
                "username": ("testshop"),
                "profile_url": ("https://www.instagram.com/" "testshop/"),
                "display_name": ("فروشگاه تست"),
                "followers_count": (25_000),
                "following_count": (100),
                "posts_count": (50),
                "category": "toys",
                "shop_score": 0.8,
                "is_shop": True,
                "bio": ("فروشگاه اسباب بازی"),
            }
        ],
    )

    write_json(
        tmp_path / "candidates.json",
        [],
    )

    write_json(
        tmp_path / "latest_discovery.json",
        {},
    )

    write_json(
        tmp_path / "latest_validation.json",
        {},
    )

    service = make_service(tmp_path)

    app = create_app(service)

    app.config["TESTING"] = True

    response = app.test_client().get("/")

    html = response.data.decode("utf-8")

    assert response.status_code == 200

    assert "@testshop" in html

    assert "25,000" in html

    assert "فروشگاه تست" in html


def test_dashboard_is_persian_and_rtl(
    tmp_path: Path,
) -> None:
    service = make_service(tmp_path)

    app = create_app(service)

    app.config["TESTING"] = True

    response = app.test_client().get("/")

    html = response.data.decode("utf-8")

    assert response.status_code == 200

    assert 'lang="fa"' in html

    assert 'dir="rtl"' in html

    assert "پنل جستجوی فروشگاه‌های اینستاگرامی" in html


def test_dashboard_filter_labels_are_persian(
    tmp_path: Path,
) -> None:
    service = make_service(tmp_path)

    app = create_app(service)

    app.config["TESTING"] = True

    response = app.test_client().get("/")

    html = response.data.decode("utf-8")

    assert response.status_code == 200

    assert "جستجو" in html

    assert "دسته‌بندی" in html

    assert "حداقل فالوور" in html

    assert "پاک کردن فیلترها" in html
