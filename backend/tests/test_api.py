import pytest
from fastapi.testclient import TestClient

from app import elexon, store
from app.main import app
from tests.synthetic import make_records


@pytest.fixture(autouse=True)
def synthetic_dataset():
    a, f = make_records()
    store.set_dataset(store.Dataset.from_records(a, f, store.Window.from_settings(), "synthetic"))
    yield
    store.set_dataset(None)


client = TestClient(app)


def test_meta():
    r = client.get("/api/meta").json()
    assert r["first_delivery_day"] == "2026-01-02" and r["last_delivery_day"] == "2026-02-01"
    assert r["n_actuals"] == 31 * 48


def test_day_endpoint_and_validation():
    assert client.get("/api/day", params={"date": "2026-01-15"}).status_code == 200
    assert client.get("/api/day", params={"date": "2025-12-01"}).status_code == 404
    assert client.get("/api/day", params={"date": "2026-01-15", "gate": "nonsense"}).status_code == 422


def test_accuracy_modes():
    d = client.get("/api/accuracy").json()
    assert d["summary"]["n"] > 600 and len(d["by_day"]) == 31
    h = client.get("/api/accuracy", params={"mode": "horizon", "horizon": 6}).json()
    assert h["summary"]["mae"] < d["summary"]["mae"]


def test_horizon_curve():
    pts = client.get("/api/horizon-curve", params={"step": 12}).json()["points"]
    assert [p["horizon_h"] for p in pts] == [0, 12, 24, 36, 48]


def test_elexon_normalisation(monkeypatch):
    raw = [
        {"publishTime": "2026-01-01T00:00:00Z", "startTime": "2026-01-02T00:00:00Z", "generation": 5},
        {"publishTime": "2026-01-01T00:00:00Z", "startTime": "2026-01-02T00:00:00Z", "generation": 6},
        {"publishTime": "2026-01-01T00:00:00Z", "startTime": "2026-01-02T01:00:00Z", "generation": None},
    ]
    monkeypatch.setattr(elexon, "_get", lambda *a, **k: raw)
    out = elexon.fetch_wind_forecasts(elexon.parse_ts("2026-01-01T00:00:00Z"),
                                      elexon.parse_ts("2026-01-01T12:00:00Z"))
    assert len(out) == 1 and out[0]["generation"] == 6.0
