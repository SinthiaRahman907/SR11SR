"""HTTP API. Thin layer: validate params -> call analysis -> JSON."""
from __future__ import annotations

import logging
from datetime import date, time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import analysis as an
from .config import settings
from .store import get_dataset

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="WindDesk API", version="1.0.0",
              description="Day-ahead wind forecast visibility and accuracy for GB national wind.")
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET"],
                   allow_headers=["*"])


def _gate(value: str) -> time:
    try:
        return time.fromisoformat(value)
    except ValueError:
        raise HTTPException(422, "gate must be HH:MM (UK local time)")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/meta")
def meta() -> dict:
    ds = get_dataset()
    w = ds.window
    pubs = ds.publish_times
    return an.to_jsonable({
        "source": ds.source,
        "loaded_at": ds.loaded_at.isoformat() if ds.loaded_at else None,
        "first_delivery_day": w.first_delivery_day.isoformat(),
        "last_delivery_day": w.last_delivery_day.isoformat(),
        "default_gate": settings.default_gate_closure.strftime("%H:%M"),
        "max_horizon_h": settings.max_horizon_h,
        "n_actuals": len(ds.actuals),
        "n_forecast_targets": len(ds.forecasts),
        "n_forecast_points": sum(len(v) for v in ds.forecasts.values()),
        "n_publications": len(pubs),
        "first_publication": pubs[0].isoformat() if pubs else None,
        "last_publication": pubs[-1].isoformat() if pubs else None,
    })


@app.get("/api/day")
def day(date_: date = Query(..., alias="date"), gate: str | None = None) -> dict:
    """Desk view for one delivery day: forecast available at gate closure,
    historical uncertainty band, and (once known) the actual outturn."""
    ds = get_dataset()
    w = ds.window
    if not (w.first_delivery_day <= date_ <= w.last_delivery_day):
        raise HTTPException(404, f"date must be between {w.first_delivery_day} and {w.last_delivery_day}")
    g = _gate(gate) if gate else settings.default_gate_closure
    return an.to_jsonable(an.day_view(ds, date_, g))


@app.get("/api/accuracy")
def accuracy(mode: an.Mode = "dayahead", gate: str | None = None,
             horizon: float = Query(24, ge=0, le=168), bin_mw: int = Query(250, ge=50, le=2000)) -> dict:
    """Accuracy over the whole January decision window.

    mode=dayahead -> forecast as known at gate closure on D-1 (what the desk used)
    mode=horizon  -> latest forecast published at least `horizon` hours before target
    """
    ds = get_dataset()
    g = _gate(gate) if gate else settings.default_gate_closure
    pairs = an.build_pairs(ds, mode, g, horizon)
    return an.to_jsonable({
        "mode": mode, "gate": g.strftime("%H:%M"), "horizon_h": horizon,
        "summary": an.summarize(pairs),
        "by_hour": an.by_hour_of_day(pairs),
        "by_day": an.by_day(pairs),
        "histogram": an.histogram(pairs, bin_mw),
        "series": an.pair_rows(pairs),
    })


@app.get("/api/horizon-curve")
def horizon_curve(step: int = Query(2, ge=1, le=12)) -> dict:
    """How error grows with lead time — explains why the D-1 decision carries risk."""
    ds = get_dataset()
    return an.to_jsonable({"points": an.by_horizon(ds, range(0, settings.max_horizon_h + 1, step))})


# ------------------------------------------------- serve built React frontend
_static = Path(__file__).resolve().parent.parent / "static"
if _static.exists():
    app.mount("/assets", StaticFiles(directory=_static / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = (_static / path).resolve()
        safe = f.is_relative_to(_static.resolve()) and f.is_file()
        return FileResponse(f if path and safe else _static / "index.html")
