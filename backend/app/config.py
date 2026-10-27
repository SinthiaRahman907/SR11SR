"""Central configuration. Every value can be overridden with an environment variable."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, time
from pathlib import Path


def _env_date(name: str, default: str) -> date:
    return date.fromisoformat(os.getenv(name, default))


@dataclass(frozen=True)
class Settings:
    elexon_base_url: str = os.getenv("ELEXON_BASE_URL", "https://data.elexon.co.uk/bmrs/api/v1")

    # Scope from the brief: purchase decisions made in January 2026.
    # A decision on day D-1 buys power for delivery day D, so decisions on
    # 1–31 Jan cover delivery days 2 Jan – 1 Feb (inclusive).
    first_decision_day: date = _env_date("FIRST_DECISION_DAY", "2026-01-01")
    last_decision_day: date = _env_date("LAST_DECISION_DAY", "2026-01-31")

    # GB day-ahead auction (N2EX/EPEX hourly) gate closure, UK local time, on D-1.
    default_gate_closure: time = time.fromisoformat(os.getenv("GATE_CLOSURE", "09:50"))

    # Longest forecast horizon analysed (hours). WINDFOR publishes ~2 days ahead.
    max_horizon_h: int = int(os.getenv("MAX_HORIZON_H", "48"))

    # Optional local snapshot so the app starts instantly and works offline.
    data_dir: Path = Path(os.getenv("DATA_DIR", str(Path(__file__).resolve().parent.parent / "data")))

    http_timeout_s: float = float(os.getenv("ELEXON_TIMEOUT_S", "30"))
    cors_origins: list[str] = field(
        default_factory=lambda: os.getenv("CORS_ORIGINS", "*").split(",")
    )


settings = Settings()
