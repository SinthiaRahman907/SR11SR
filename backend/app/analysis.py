"""Pure analysis functions: forecast selection and accuracy metrics.

Sign convention used everywhere:  error = forecast - actual  (MW)
  error > 0  -> over-forecast: less wind turned up than planned -> desk is SHORT
  error < 0  -> under-forecast: more wind than planned            -> desk is LONG
"""
from __future__ import annotations

import math
import statistics
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from typing import Iterable, Literal

from .store import LONDON, Dataset

Mode = Literal["dayahead", "horizon"]


@dataclass(frozen=True)
class Pair:
    start: datetime
    actual: float
    forecast: float
    publish: datetime

    @property
    def error(self) -> float:
        return self.forecast - self.actual

    @property
    def horizon_h(self) -> float:
        return (self.start - self.publish).total_seconds() / 3600


# ------------------------------------------------------------ forecast choice

def delivery_day(start: datetime) -> date:
    return start.astimezone(LONDON).date()


def gate_cutoff(day: date, gate: time) -> datetime:
    """Decision moment for delivery day `day`: gate closure (UK time) on D-1."""
    return datetime.combine(day - timedelta(days=1), gate, tzinfo=LONDON)


def cutoff_for(start: datetime, mode: Mode, gate: time, horizon_h: float) -> datetime:
    if mode == "dayahead":
        return gate_cutoff(delivery_day(start), gate)
    return start - timedelta(hours=horizon_h)


def build_pairs(ds: Dataset, mode: Mode = "dayahead", gate: time = time(9, 50),
                horizon_h: float = 24, days: Iterable[date] | None = None) -> list[Pair]:
    """Forecast/actual pairs, choosing for every target the latest forecast
    that was available at the decision moment."""
    wanted = set(days) if days is not None else None
    out: list[Pair] = []
    for start in ds.target_times:
        if wanted is not None and delivery_day(start) not in wanted:
            continue
        actual = ds.actuals.get(start)
        if actual is None:
            continue
        fc = ds.latest_forecast(start, cutoff_for(start, mode, gate, horizon_h))
        if fc is None:
            continue
        out.append(Pair(start, actual, fc[1], fc[0]))
    return out


# ------------------------------------------------------------------ metrics

def quantile(sorted_vals: list[float], q: float) -> float:
    """Linear-interpolated quantile of an already-sorted list."""
    if not sorted_vals:
        return math.nan
    pos = (len(sorted_vals) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def summarize(pairs: list[Pair]) -> dict:
    if not pairs:
        return {"n": 0}
    errs = [p.error for p in pairs]
    abs_errs = sorted(abs(e) for e in errs)
    s = sorted(errs)
    mean_actual = statistics.fmean(p.actual for p in pairs)
    mae = statistics.fmean(abs_errs)
    return {
        "n": len(pairs),
        "mae": mae,
        "rmse": math.sqrt(statistics.fmean(e * e for e in errs)),
        "bias": statistics.fmean(errs),
        "nmae_pct": 100 * mae / mean_actual if mean_actual else None,
        "mean_actual": mean_actual,
        "median_abs": quantile(abs_errs, 0.5),
        "p90_abs": quantile(abs_errs, 0.9),
        "p10": quantile(s, 0.1),
        "p50": quantile(s, 0.5),
        "p90": quantile(s, 0.9),
        "max_over": max(errs),
        "max_under": min(errs),
        "pct_over": 100 * sum(e > 0 for e in errs) / len(errs),
        "mean_horizon_h": statistics.fmean(p.horizon_h for p in pairs),
    }


def _compact(m: dict, keys: tuple[str, ...]) -> dict:
    return {k: m.get(k) for k in keys}


def by_horizon(ds: Dataset, horizons: Iterable[int]) -> list[dict]:
    keys = ("n", "mae", "rmse", "bias", "p10", "p90", "nmae_pct")
    return [{"horizon_h": h, **_compact(summarize(build_pairs(ds, "horizon", horizon_h=h)), keys)}
            for h in horizons]


def by_hour_of_day(pairs: list[Pair]) -> list[dict]:
    buckets: dict[int, list[Pair]] = {}
    for p in pairs:
        buckets.setdefault(p.start.astimezone(LONDON).hour, []).append(p)
    keys = ("n", "mae", "bias", "p10", "p90")
    return [{"hour": h, **_compact(summarize(buckets[h]), keys)} for h in sorted(buckets)]


def by_day(pairs: list[Pair]) -> list[dict]:
    buckets: dict[date, list[Pair]] = {}
    for p in pairs:
        buckets.setdefault(delivery_day(p.start), []).append(p)
    keys = ("n", "mae", "bias", "mean_actual")
    return [{"day": d.isoformat(), **_compact(summarize(buckets[d]), keys)} for d in sorted(buckets)]


def histogram(pairs: list[Pair], bin_mw: int = 250) -> list[dict]:
    if not pairs:
        return []
    counts: dict[int, int] = {}
    for p in pairs:
        b = math.floor(p.error / bin_mw)
        counts[b] = counts.get(b, 0) + 1
    lo, hi = min(counts), max(counts)
    n = len(pairs)
    return [{"from": b * bin_mw, "to": (b + 1) * bin_mw, "count": counts.get(b, 0),
             "pct": 100 * counts.get(b, 0) / n} for b in range(lo, hi + 1)]


def pair_rows(pairs: list[Pair]) -> list[dict]:
    return [{"time": p.start.isoformat(), "actual": p.actual, "forecast": p.forecast,
             "error": p.error, "publishTime": p.publish.isoformat(),
             "horizon_h": round(p.horizon_h, 2)} for p in pairs]


# -------------------------------------------------------- day-ahead desk view

MIN_HISTORY_PAIRS = 48  # two days of hourly pairs before we trust a trailing band


def error_band(ds: Dataset, day: date, gate: time) -> dict:
    """P10/P90 of day-ahead errors using only delivery days BEFORE `day`
    (what the desk would genuinely have known). Falls back to the whole
    period, flagged as in-sample, when there is too little history."""
    prior_days = [d for d in {delivery_day(t) for t in ds.target_times} if d < day]
    hist = build_pairs(ds, "dayahead", gate, days=prior_days)
    basis = "trailing"
    if len(hist) < MIN_HISTORY_PAIRS:
        hist, basis = build_pairs(ds, "dayahead", gate), "full-period (in-sample)"
    s = sorted(p.error for p in hist)
    return {"p10": quantile(s, 0.1), "p50": quantile(s, 0.5), "p90": quantile(s, 0.9),
            "n": len(s), "basis": basis}


def _step_hours(times: list[datetime]) -> float:
    if len(times) < 2:
        return 1.0
    diffs = sorted((b - a).total_seconds() / 3600 for a, b in zip(times, times[1:]))
    return diffs[len(diffs) // 2]


def day_view(ds: Dataset, day: date, gate: time) -> dict:
    cutoff = gate_cutoff(day, gate)
    band = error_band(ds, day, gate)
    day_start = datetime.combine(day, time(0), tzinfo=LONDON)
    day_end = datetime.combine(day + timedelta(days=1), time(0), tzinfo=LONDON)

    rows, used_pubs = [], set()
    for start in ds.target_times:
        if not (day_start <= start < day_end):
            continue
        fc = ds.latest_forecast(start, cutoff)
        if fc is None:
            continue
        pub, f = fc
        used_pubs.add(pub)
        lo = max(0.0, f - band["p90"]) if not math.isnan(band["p90"]) else None
        hi = max(0.0, f - band["p10"]) if not math.isnan(band["p10"]) else None
        rows.append({"time": start.isoformat(), "forecast": f, "publishTime": pub.isoformat(),
                     "horizon_h": round((start - pub).total_seconds() / 3600, 2),
                     "p90_wind": lo, "p10_wind": hi, "actual_at_forecast": ds.actuals.get(start)})

    actual_rows = [{"time": t.isoformat(), "actual": v} for t, v in sorted(ds.actuals.items())
                   if day_start <= t < day_end]

    step = _step_hours([datetime.fromisoformat(r["time"]) for r in rows])
    totals = {
        "forecast_mwh": sum(r["forecast"] for r in rows) * step,
        "p90_wind_mwh": sum(r["p90_wind"] or 0 for r in rows) * step if rows else None,
        "actual_mwh": (sum(r["actual"] for r in actual_rows) * 0.5) if len(actual_rows) == 48 else None,
    }
    pairs = [Pair(datetime.fromisoformat(r["time"]), r["actual_at_forecast"], r["forecast"],
                  datetime.fromisoformat(r["publishTime"]))
             for r in rows if r["actual_at_forecast"] is not None]
    return {
        "day": day.isoformat(),
        "cutoff": cutoff.isoformat(),
        "forecast_publish_times": sorted(p.isoformat() for p in used_pubs),
        "band": band,
        "forecast": rows,
        "actual": actual_rows,
        "totals": totals,
        "realised": summarize(pairs),
    }


def to_jsonable(obj):
    if isinstance(obj, float) and math.isnan(obj):
        return None
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_jsonable(v) for v in obj]
    if hasattr(obj, "__dataclass_fields__"):
        return to_jsonable(asdict(obj))
    return obj
