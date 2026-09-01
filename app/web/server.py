from __future__ import annotations

from typing import Any

from flask import (
    Flask,
    render_template,
)

from app.config import (
    CANDIDATES_FILE,
    LATEST_DISCOVERY_FILE,
    LATEST_VALIDATION_FILE,
    PROFILES_FILE,
)
from app.web.dashboard_service import (
    DashboardService,
)


def format_number(
    value: Any,
) -> str:
    if value is None:
        return "-"

    try:
        number = int(value)
    except (
        TypeError,
        ValueError,
    ):
        return str(value)

    return f"{number:,}"


def format_score(
    value: Any,
) -> str:
    if value is None:
        return "-"

    try:
        number = float(value)
    except (
        TypeError,
        ValueError,
    ):
        return "-"

    return f"{number * 100:.0f}%"


def create_app(
    service: DashboardService | None = None,
) -> Flask:
    app = Flask(
        __name__,
    )

    dashboard_service = service or DashboardService(
        profiles_file=(PROFILES_FILE),
        candidates_file=(CANDIDATES_FILE),
        latest_discovery_file=(LATEST_DISCOVERY_FILE),
        latest_validation_file=(LATEST_VALIDATION_FILE),
    )

    app.jinja_env.filters["number"] = format_number

    app.jinja_env.filters["score"] = format_score

    @app.get("/")
    def dashboard():
        data = dashboard_service.get_dashboard_data()

        return render_template(
            "dashboard.html",
            stats=data.stats,
            profiles=data.profiles,
            candidates=data.candidates,
            latest_discovery=(data.latest_discovery),
            latest_validation=(data.latest_validation),
        )

    return app


app = create_app()


def main() -> None:
    print()
    print("Instagram Shop Finder Dashboard")
    print("=================================")
    print()
    print("Open in browser:")
    print("http://127.0.0.1:8000")
    print()

    app.run(
        host="127.0.0.1",
        port=8000,
        debug=False,
    )


if __name__ == "__main__":
    main()
