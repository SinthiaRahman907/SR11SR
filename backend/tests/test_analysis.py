from datetime import date, datetime, time, timezone

import pytest

from app import analysis as an
from app.store import Dataset, Window

UTC = timezone.utc
W = Window(date(2026, 1, 2), date(2026, 2, 1))


def ts(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=UTC)


@pytest.fixture
def tiny() -> Dataset:
    target = ts("2026-01-10T12:00")
    forecasts = [
        {"publishTime": ts("2026-01-08T12:00"), "startTime": target, "generation": 1000},
        {"publishTime": ts("2026-01-09T09:50"), "startTime": target, "generation": 1100},  # exactly at gate
        {"publishTime": ts("2026-01-09T10:00"), "startTime": target, "generation": 1200},  # after gate
        {"publishTime": ts("2026-01-10T08:00"), "startTime": target, "generation": 1300},
    ]
    actuals = [{"startTime": target, "publishTime": target, "generation": 1250}]
    return Dataset.from_records(actuals, forecasts, W, "test")


def test_dayahead_uses_latest_forecast_at_or_before_gate(tiny):
    [p] = an.build_pairs(tiny, "dayahead", time(9, 50))
    assert p.forecast == 1100 and p.publish == ts("2026-01-09T09:50")
    assert p.error == -150  # forecast - actual


def test_gate_time_changes_choice(tiny):
    [p] = an.build_pairs(tiny, "dayahead", time(9, 0))
    assert p.forecast == 1000


def test_horizon_mode(tiny):
    assert an.build_pairs(tiny, "horizon", horizon_h=4)[0].forecast == 1300
    assert an.build_pairs(tiny, "horizon", horizon_h=26)[0].forecast == 1200
    assert an.build_pairs(tiny, "horizon", horizon_h=72) == []  # nothing published that early


def test_targets_outside_window_ignored():
    fc = [{"publishTime": ts("2026-01-01T00:00"), "startTime": ts("2026-01-01T12:00"), "generation": 1}]
    ds = Dataset.from_records([], fc, W, "test")
    assert ds.target_times == []


def test_summary_metrics():
    t = ts("2026-01-05T00:00")
    pairs = [an.Pair(t, 100, 110, t), an.Pair(t, 100, 80, t), an.Pair(t, 100, 100, t)]
    m = an.summarize(pairs)
    assert m["n"] == 3
    assert m["mae"] == pytest.approx(10)
    assert m["bias"] == pytest.approx(-10 / 3)
    assert m["rmse"] == pytest.approx((500 / 3) ** 0.5)
    assert m["nmae_pct"] == pytest.approx(10)
    assert m["max_over"] == 10 and m["max_under"] == -20


def test_quantile_interpolates():
    assert an.quantile([0, 10], 0.5) == 5
    assert an.quantile([1, 2, 3, 4, 5], 0.9) == pytest.approx(4.6)


def test_histogram_counts_everything():
    t = ts("2026-01-05T00:00")
    pairs = [an.Pair(t, 0, e, t) for e in (-300, -10, 10, 260, 499)]
    h = an.histogram(pairs, 250)
    assert sum(b["count"] for b in h) == 5
    assert h[0]["from"] == -500 and h[-1]["to"] == 500


def test_day_view_band_uses_only_prior_days():
    from tests.synthetic import make_records
    a, f = make_records()
    ds = Dataset.from_records(a, f, W, "synthetic")
    early = an.day_view(ds, date(2026, 1, 2), time(9, 50))
    later = an.day_view(ds, date(2026, 1, 20), time(9, 50))
    assert early["band"]["basis"].startswith("full-period")
    assert later["band"]["basis"] == "trailing"
    assert len(later["actual"]) == 48 and len(later["forecast"]) == 24
    for r in later["forecast"]:
        assert r["p90_wind"] <= r["p10_wind"]
        assert datetime.fromisoformat(r["publishTime"]) <= datetime.fromisoformat(later["cutoff"])


def test_error_grows_with_horizon_on_synthetic():
    from tests.synthetic import make_records
    a, f = make_records()
    ds = Dataset.from_records(a, f, W, "synthetic")
    curve = an.by_horizon(ds, [2, 24, 46])
    assert curve[0]["mae"] < curve[1]["mae"] < curve[2]["mae"]
