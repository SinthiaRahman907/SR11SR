# WindDesk — day-ahead wind forecast visibility & accuracy

A web app for a UK utility's day-ahead trading desk. It answers two questions for every
purchase decision made in **January 2026**:

1. **What did the latest wind forecast say when we had to buy?** — the forecast available at
   day-ahead gate closure on D-1, with an uncertainty band built only from errors seen on
   earlier days.
2. **How much can we trust it?** — quantified error (MAE, RMSE, bias, P10/P90), how error
   grows with lead time, and where in the day and month it goes wrong.

Data: Elexon BMRS, national level only — actuals from `FUELHH` (`fuelType = WIND`),
forecasts from `WINDFOR`.

**Live app:** _<add your Vercel / Heroku URL here>_

---

## Key definitions

| Term | Meaning in this app |
|---|---|
| Decision window | Purchases made 1–31 Jan 2026 → delivery days **2 Jan – 1 Feb 2026** |
| Gate closure | GB day-ahead auction (N2EX/EPEX hourly) closes **09:50 UK time on D-1**; editable in the header |
| Forecast "as used" | For each target hour, the latest `WINDFOR` forecast with `publishTime ≤ gate closure on D-1` |
| Fixed lead time *h* | Latest forecast with `publishTime ≤ startTime − h` |
| Error | `forecast − actual` (MW). **Positive = over-forecast → desk is short of wind** |
| P90 wind | Forecast minus the 90th-percentile historical error: wind you'd expect to *exceed* 90% of the time |
| Uncertainty band | P10–P90 of day-ahead errors from **previous delivery days only** (no look-ahead). The first two days fall back to the full month and are labelled *in-sample* |

Forecasts are hourly; actuals are half-hourly. Pairs are matched on identical `startTime`.

## Repository layout

```
.
├── backend/                 Python API (FastAPI)
│   ├── app/
│   │   ├── config.py        Settings (env-overridable): window, gate closure, horizons
│   │   ├── elexon.py        Elexon client: chunked requests, retries, normalisation, de-dup
│   │   ├── store.py         In-memory dataset + JSON snapshot; fast "latest forecast before t" lookup
│   │   ├── analysis.py      Pure functions: forecast selection, metrics, bands, histograms
│   │   └── main.py          HTTP routes; also serves the built frontend
│   ├── scripts/snapshot.py  Pull the January window from Elexon into backend/data/
│   ├── tests/               pytest: unit tests for analysis + API tests (synthetic data)
│   ├── data/                Snapshot JSON (optional, makes start-up instant)
│   └── requirements*.txt
├── frontend/                React + TypeScript + Vite + Recharts
│   └── src/
│       ├── App.tsx          Shell, tabs, gate-closure control
│       ├── DayAhead.tsx     Desk view for one delivery day
│       ├── Accuracy.tsx     Accuracy analytics across the window
│       ├── api.ts           Typed API client
│       ├── ui.tsx, colors.ts, format.ts, styles.css
├── api/index.py             Vercel serverless entry (wraps backend app)
├── Dockerfile               Multi-stage: build React, run FastAPI serving both
├── docker-compose.yml, heroku.yml, vercel.json
└── docs/VIDEO_SCRIPT.md     Talking points for the client pitch and tech review
```

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/meta` | Data coverage, window, default gate |
| `GET /api/day?date=2026-01-20&gate=09:50` | Forecast used, band, P90 wind, actual outturn for one delivery day |
| `GET /api/accuracy?mode=dayahead&gate=09:50` | Metrics, hour-of-day, daily, histogram, full series |
| `GET /api/accuracy?mode=horizon&horizon=24` | Same, at a fixed lead time |
| `GET /api/horizon-curve?step=2` | MAE and P10/P90 by lead time 0–48 h |

Interactive docs at `/docs` when the server is running.

## Running it

### Docker (recommended)
```bash
docker compose up --build      # → http://localhost:8000
```

### Local development
```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m scripts.snapshot     # optional: cache Elexon data to backend/data/
uvicorn app.main:app --reload  # → http://localhost:8000/docs
pytest -q

# frontend (second terminal)
cd frontend
npm install
npm run dev                    # → http://localhost:5173 (proxies /api to :8000)
```

Without a snapshot the backend fetches from Elexon on first request (~10–30 s), then keeps
the data in memory.

### Deploy
- **Vercel:** commit `backend/data/*.json` (run the snapshot script first), then `vercel --prod`
  from the repo root. `vercel.json` builds the frontend and exposes the API as a Python function.
- **Heroku:** `heroku stack:set container && git push heroku main` (uses `heroku.yml` + Dockerfile).

## Design notes

- **Analysis is pure and tested.** `analysis.py` has no I/O; the API layer only validates
  parameters and serialises. Forecast lookup uses a per-target sorted list of publish times
  and `bisect`, so any cutoff query is O(log n).
- **No look-ahead.** The day view's uncertainty band uses only earlier delivery days, so it
  shows what the desk could genuinely have known.
- **Snapshot first, live fallback.** Fast, reproducible demos; still works from a clean
  checkout. Read-only filesystems (serverless) just skip writing the snapshot.
- **Small dependency set** (FastAPI, httpx, uvicorn; no pandas) for quick cold starts.
- **Limitations / next steps:** national wind only (no solar or demand); quantile band is
  empirical and not conditioned on wind level; no scheduled refresh for live operation.

## Use of AI tools

This project was built with help from an AI assistant (Claude, by Anthropic), which drafted
code, tests and documentation. All design decisions, results and code were reviewed by me.
