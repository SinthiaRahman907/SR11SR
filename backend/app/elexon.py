"""Thin client for the two Elexon BMRS stream endpoints the product uses.

* FUELHH  – half-hourly outturn by fuel type (we keep fuelType == WIND)
* WINDFOR – national wind generation forecasts, many publications per day

Requests are split into small date chunks (the stream endpoints are happiest
with short ranges) and retried with back-off. Records are normalised to plain
dicts with timezone-aware UTC datetimes so the analysis layer never sees raw
API JSON.
"""
from __future__ import annotations

import logging
import time as _time
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

import httpx

from .config import settings

log = logging.getLogger(__name__)


def parse_ts(value: str) -> datetime:
    """Parse Elexon ISO timestamps ("2026-01-02T00:00:00Z") to aware UTC."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get(client: httpx.Client, path: str, params: dict, attempts: int = 4) -> list[dict]:
    url = f"{settings.elexon_base_url}{path}"
    for attempt in range(1, attempts + 1):
        try:
            r = client.get(url, params=params)
            r.raise_for_status()
            body = r.json()
            # stream endpoints return a bare list; non-stream ones wrap in {"data": [...]}
            return body["data"] if isinstance(body, dict) else body
        except (httpx.HTTPError, ValueError) as exc:
            if attempt == attempts:
                raise
            wait = 2 ** attempt
            log.warning("Elexon %s failed (%s); retry %d in %ss", path, exc, attempt, wait)
            _time.sleep(wait)
    return []  # unreachable


def _chunks(start: datetime, end: datetime, step: timedelta) -> Iterable[tuple[datetime, datetime]]:
    cur = start
    while cur < end:
        nxt = min(cur + step, end)
        yield cur, nxt
        cur = nxt


def fetch_wind_forecasts(publish_from: datetime, publish_to: datetime) -> list[dict]:
    """All WINDFOR rows published in [publish_from, publish_to)."""
    rows: dict[tuple[str, str], dict] = {}
    with httpx.Client(timeout=settings.http_timeout_s) as client:
        for a, b in _chunks(publish_from, publish_to, timedelta(days=2)):
            raw = _get(client, "/datasets/WINDFOR/stream", {
                "publishDateTimeFrom": iso_z(a),
                "publishDateTimeTo": iso_z(b),
            })
            for r in raw:
                if r.get("generation") is None:
                    continue
                pub, start = parse_ts(r["publishTime"]), parse_ts(r["startTime"])
                if not (publish_from <= pub < publish_to):
                    continue  # chunk boundaries are inclusive on Elexon's side
                rows[(iso_z(pub), iso_z(start))] = {
                    "publishTime": pub, "startTime": start, "generation": float(r["generation"]),
                }
    out = sorted(rows.values(), key=lambda r: (r["startTime"], r["publishTime"]))
    log.info("WINDFOR: %d forecast points", len(out))
    return out


def fetch_wind_actuals(settlement_from: date, settlement_to: date) -> list[dict]:
    """WIND outturn for settlement dates [settlement_from, settlement_to] inclusive.

    FUELHH can be republished; for each startTime we keep the latest publication.
    """
    latest: dict[str, dict] = {}
    with httpx.Client(timeout=settings.http_timeout_s) as client:
        day = settlement_from
        while day <= settlement_to:
            to = min(day + timedelta(days=6), settlement_to)
            raw = _get(client, "/datasets/FUELHH/stream", {
                "settlementDateFrom": day.isoformat(),
                "settlementDateTo": to.isoformat(),
                "fuelType": "WIND",
            })
            for r in raw:
                if r.get("fuelType") != "WIND" or r.get("generation") is None:
                    continue
                start = parse_ts(r["startTime"])
                pub = parse_ts(r["publishTime"]) if r.get("publishTime") else start
                key = iso_z(start)
                if key not in latest or pub >= latest[key]["publishTime"]:
                    latest[key] = {"startTime": start, "publishTime": pub,
                                   "generation": float(r["generation"])}
            day = to + timedelta(days=1)
    out = sorted(latest.values(), key=lambda r: r["startTime"])
    log.info("FUELHH WIND: %d half-hours", len(out))
    return out
