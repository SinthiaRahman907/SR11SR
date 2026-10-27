"""In-memory dataset with an optional on-disk JSON snapshot.

Load order: snapshot in DATA_DIR (fast, offline) -> live Elexon fetch.
After a live fetch we try to write the snapshot so the next start is instant
(silently skipped on read-only filesystems such as serverless platforms).
"""
from __future__ import annotations

import bisect
import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from . import elexon
from .config import settings

log = logging.getLogger(__name__)
LONDON = ZoneInfo("Europe/London")


def london_midnight(d: date) -> datetime:
    return datetime.combine(d, time(0), tzinfo=LONDON)


@dataclass
class Window:
    """Time window implied by 'purchase decisions made in January 2026'."""
    first_delivery_day: date
    last_delivery_day: date

    @classmethod
    def from_settings(cls) -> "Window":
        return cls(settings.first_decision_day + timedelta(days=1),
                   settings.last_decision_day + timedelta(days=1))

    @property
    def delivery_start(self) -> datetime:
        return london_midnight(self.first_delivery_day)

    @property
    def delivery_end(self) -> datetime:  # exclusive
        return london_midnight(self.last_delivery_day + timedelta(days=1))

    @property
    def publish_from(self) -> datetime:
        # enough history to evaluate the longest horizon for the first target
        return self.delivery_start - timedelta(hours=settings.max_horizon_h + 24)

    @property
    def publish_to(self) -> datetime:
        return self.delivery_end


@dataclass
class Dataset:
    actuals: dict[datetime, float]
    # startTime -> list of (publishTime, generation), sorted by publishTime
    forecasts: dict[datetime, list[tuple[datetime, float]]]
    window: Window
    source: str = "unknown"
    loaded_at: datetime | None = None
    _pub_keys: dict[datetime, list[datetime]] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        for start, series in self.forecasts.items():
            series.sort(key=lambda p: p[0])
            self._pub_keys[start] = [p for p, _ in series]

    @classmethod
    def from_records(cls, actuals: list[dict], forecasts: list[dict], window: Window,
                     source: str) -> "Dataset":
        act = {r["startTime"]: r["generation"] for r in actuals
               if window.delivery_start <= r["startTime"] < window.delivery_end}
        fc: dict[datetime, list[tuple[datetime, float]]] = {}
        for r in forecasts:
            if window.delivery_start <= r["startTime"] < window.delivery_end:
                fc.setdefault(r["startTime"], []).append((r["publishTime"], r["generation"]))
        return cls(act, fc, window, source, datetime.now(tz=LONDON))

    def latest_forecast(self, start: datetime, cutoff: datetime) -> tuple[datetime, float] | None:
        """Most recent forecast for `start` published at or before `cutoff`."""
        keys = self._pub_keys.get(start)
        if not keys:
            return None
        i = bisect.bisect_right(keys, cutoff)
        return self.forecasts[start][i - 1] if i else None

    @property
    def target_times(self) -> list[datetime]:
        return sorted(self.forecasts)

    @property
    def publish_times(self) -> list[datetime]:
        return sorted({p for s in self.forecasts.values() for p, _ in s})


# ---------------------------------------------------------------- persistence

def _dump(records: list[dict]) -> list[dict]:
    return [{k: (elexon.iso_z(v) if isinstance(v, datetime) else v) for k, v in r.items()}
            for r in records]


def _load(records: list[dict]) -> list[dict]:
    return [{k: (elexon.parse_ts(v) if k.endswith("Time") else v) for k, v in r.items()}
            for r in records]


def load_snapshot(window: Window) -> Dataset | None:
    a, f = settings.data_dir / "actuals.json", settings.data_dir / "forecasts.json"
    if not (a.exists() and f.exists()):
        return None
    actuals = _load(json.loads(a.read_text()))
    forecasts = _load(json.loads(f.read_text()))
    log.info("Loaded snapshot from %s", settings.data_dir)
    return Dataset.from_records(actuals, forecasts, window, source="snapshot")


def fetch_live(window: Window) -> tuple[list[dict], list[dict]]:
    actuals = elexon.fetch_wind_actuals(window.first_delivery_day - timedelta(days=1),
                                        window.last_delivery_day + timedelta(days=1))
    forecasts = elexon.fetch_wind_forecasts(window.publish_from, window.publish_to)
    return actuals, forecasts


def save_snapshot(actuals: list[dict], forecasts: list[dict]) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "actuals.json").write_text(json.dumps(_dump(actuals)))
    (settings.data_dir / "forecasts.json").write_text(json.dumps(_dump(forecasts)))


_lock = threading.Lock()
_dataset: Dataset | None = None


def get_dataset() -> Dataset:
    global _dataset
    if _dataset is not None:
        return _dataset
    with _lock:
        if _dataset is None:
            window = Window.from_settings()
            ds = load_snapshot(window)
            if ds is None:
                actuals, forecasts = fetch_live(window)
                ds = Dataset.from_records(actuals, forecasts, window, source="elexon-live")
                try:
                    save_snapshot(actuals, forecasts)
                except OSError as exc:  # read-only FS (e.g. serverless)
                    log.info("Snapshot not written: %s", exc)
            _dataset = ds
    return _dataset


def set_dataset(ds: Dataset | None) -> None:
    """Test hook / manual refresh."""
    global _dataset
    _dataset = ds
