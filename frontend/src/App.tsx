import { useState } from "react";
import { api } from "./api";
import Accuracy from "./Accuracy";
import DayAhead from "./DayAhead";
import { ukDateTime } from "./format";
import { Status, useAsync } from "./ui";

type Tab = "day" | "accuracy";

export default function App() {
  const [tab, setTab] = useState<Tab>("day");
  const [gate, setGate] = useState<string | null>(null);
  const meta = useAsync(() => api.meta(), []);
  const g = gate ?? meta.data?.default_gate ?? "09:50";

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <span className="logo" aria-hidden>
            <svg viewBox="0 0 24 24" width="22" height="22"><path d="M3 8h11a3 3 0 1 0-3-3M3 12h15a3 3 0 1 1-3 3M3 16h8" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>
          </span>
          <div>
            <h1>WindDesk</h1>
            <p>GB national wind · day-ahead procurement view</p>
          </div>
        </div>
        <nav className="tabs" role="tablist">
          <button role="tab" aria-selected={tab === "day"} className={tab === "day" ? "on" : ""} onClick={() => setTab("day")}>Day-ahead view</button>
          <button role="tab" aria-selected={tab === "accuracy"} className={tab === "accuracy" ? "on" : ""} onClick={() => setTab("accuracy")}>Forecast accuracy</button>
        </nav>
        <label className="gate">
          <span>Gate closure (D-1, UK)</span>
          <input type="time" value={g} onChange={(e) => e.target.value && setGate(e.target.value)} />
        </label>
      </header>

      <main>
        <Status loading={meta.loading} error={meta.error} />
        {meta.data && (tab === "day" ? <DayAhead meta={meta.data} gate={g} /> : <Accuracy meta={meta.data} gate={g} />)}
      </main>

      {meta.data && (
        <footer>
          Data: Elexon BMRS — actuals FUELHH (fuelType WIND), forecasts WINDFOR · {meta.data.n_publications} forecast
          publications{meta.data.last_publication && <> up to {ukDateTime(meta.data.last_publication)}</>} · source: {meta.data.source}.
          Decisions for delivery days {meta.data.first_delivery_day} → {meta.data.last_delivery_day} (bought 1–31 Jan 2026).
        </footer>
      )}
    </div>
  );
}
