"""Deterministic synthetic Elexon-shaped data for tests (never used in the product)."""
from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone


def make_records(seed: int = 7):
    rng = random.Random(seed)
    t0 = datetime(2025, 12, 30, tzinfo=timezone.utc)
    t1 = datetime(2026, 2, 3, tzinfo=timezone.utc)

    def truth(t: datetime) -> float:
        h = (t - t0).total_seconds() / 3600
        return max(0.0, 9000 + 5000 * math.sin(h / 37) + 2500 * math.sin(h / 9 + 1))

    actuals, t = [], t0
    while t < t1:
        actuals.append({"startTime": t, "publishTime": t + timedelta(minutes=35),
                        "generation": round(truth(t) + rng.gauss(0, 150), 1)})
        t += timedelta(minutes=30)

    forecasts, pub = [], t0
    while pub < t1:
        start = pub.replace(minute=0) + timedelta(hours=1)
        while start <= pub + timedelta(hours=48):
            lead = (start - pub).total_seconds() / 3600
            err = rng.gauss(150, 120 + 25 * lead)  # error grows with lead time, slight over-bias
            forecasts.append({"publishTime": pub, "startTime": start,
                              "generation": round(max(0.0, truth(start) + err), 1)})
            start += timedelta(hours=1)
        pub += timedelta(hours=3, minutes=30)
    return actuals, forecasts
