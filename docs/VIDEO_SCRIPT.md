# Video talking points (≤10 min total)

Replace the bracketed numbers with what the app shows on **real** Elexon data before recording.

## Part 1 — Client pitch (≤5 min)

**0:00 Problem (30 s)**
"Every morning before 09:50 your desk commits to day-ahead volumes. Wind can swing by
gigawatts, and you're buying against a forecast. If wind under-delivers you're short and
exposed to imbalance prices; if it over-delivers you've overpaid for thermal."

**0:30 Day-ahead view (1 m 45 s)**
- Pick a delivery day. Point at the decision strip: the exact forecast that was live at gate
  closure, when it was published, and the lead time (≈14–38 h).
- Headline tiles: forecast energy, **P90 wind** ("the wind you can count on 9 days in 10"),
  typical error range.
- Chart: orange forecast, blue band, blue actual. Show a calm day, then the worst day from the
  accuracy page — the band is wide for a reason.
- Mention the band uses only *previous* days — it's honest about what you knew at the time.
- Change gate closure to show it's configurable to your desk's process.

**2:15 Accuracy (2 m)**
- Headline sentence: D-1 forecast off by [X MW] on average, [Y %] of mean wind; 80% of hours
  within [a … b].
- Bias: [over/under-forecast by N MW] → actionable: shade purchases accordingly.
- Error-vs-lead-time curve: error roughly [doubles] from 6 h to 36 h — quantifies the cost of
  committing a day early; supports intraday re-balancing.
- Hour-of-day bars: which delivery blocks are riskiest to hedge.
- Daily bars: drill from a bad day into the Day-ahead view.

**4:15 Close (45 s)**
Pilot outcome, next phase: add solar and demand to get net procurement need, live daily
refresh, alerting when the band is wide, and a P-value selector tied to your risk appetite.

## Part 2 — Tech lead review (≤5 min)

**0:00 Architecture (1 m)** — one container: Vite/React build served by FastAPI. Backend
layers: `elexon.py` (I/O) → `store.py` (in-memory dataset + snapshot) → `analysis.py` (pure)
→ `main.py` (thin routes). Vercel variant wraps the same app as a serverless function.

**1:00 Data handling (1 m 15 s)**
- Window maths: decisions 1–31 Jan → delivery 2 Jan–1 Feb; WINDFOR fetched from 72 h before
  the first target so every lead time up to 48 h is covered.
- Chunked requests + retries; dedupe on (publishTime, startTime); FUELHH keeps the latest
  revision per half hour.
- Times are UTC internally; gate closure is UK local via `zoneinfo` (DST-safe).

**2:15 Core logic (1 m 15 s)**
- `latest_forecast(start, cutoff)` = bisect over sorted publish times.
- Two selection modes share one function (`cutoff_for`).
- Metrics: MAE, RMSE, bias, nMAE, interpolated quantiles; signed convention documented.
- Band without look-ahead, with explicit in-sample fallback flag.

**3:30 Quality (1 m)** — pytest: boundary cases (forecast published exactly at gate, after
gate), metric maths, window filtering, API validation, Elexon normalisation with the HTTP layer
mocked. Typed frontend, theme tokens, light/dark, accessible table view.

**4:30 Trade-offs & next steps (30 s)** — no pandas (cold start), JSON snapshot instead of a
DB (dataset is ~10⁴ rows), next: scheduled refresh, persistence, CI.
