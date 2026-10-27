import { useMemo, useState } from "react";
import {
  Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api, Meta } from "./api";
import { usePalette } from "./colors";
import { addDays, gwh, kfmt, longDay, mw, signedMw, ukDateTime, ukTime } from "./format";
import { Kpi, Panel, Status, Swatch, useAsync } from "./ui";

interface Row {
  t: number;
  actual?: number;
  forecast?: number;
  band?: [number, number];
}

export default function DayAhead({ meta, gate }: { meta: Meta; gate: string }) {
  const [day, setDay] = useState(meta.first_delivery_day);
  const [showTable, setShowTable] = useState(false);
  const { data, loading, error } = useAsync(() => api.day(day, gate), [day, gate]);
  const c = usePalette();

  const rows = useMemo<Row[]>(() => {
    if (!data) return [];
    const m = new Map<number, Row>();
    const at = (iso: string) => {
      const t = Date.parse(iso);
      if (!m.has(t)) m.set(t, { t });
      return m.get(t)!;
    };
    data.actual.forEach((a) => (at(a.time).actual = a.actual));
    data.forecast.forEach((f) => {
      const r = at(f.time);
      r.forecast = f.forecast;
      if (f.p90_wind != null && f.p10_wind != null) r.band = [f.p90_wind, f.p10_wind];
    });
    return [...m.values()].sort((a, b) => a.t - b.t);
  }, [data]);

  const first = meta.first_delivery_day, last = meta.last_delivery_day;
  const pubs = data?.forecast_publish_times ?? [];
  const latestPub = pubs[pubs.length - 1];
  const leadMin = latestPub && data ? Math.round((Date.parse(data.cutoff) - Date.parse(latestPub)) / 60000) : null;
  const horizons = data?.forecast.map((f) => f.horizon_h) ?? [];
  const realised = data?.realised;

  return (
    <>
      <div className="toolbar">
        <div className="day-picker">
          <button onClick={() => setDay(addDays(day, -1))} disabled={day <= first} aria-label="Previous day">‹</button>
          <input type="date" value={day} min={first} max={last} onChange={(e) => e.target.value && setDay(e.target.value)} />
          <button onClick={() => setDay(addDays(day, 1))} disabled={day >= last} aria-label="Next day">›</button>
        </div>
        <div className="toolbar-title">
          <span className="eyebrow">Delivery day</span>
          <strong>{longDay(day)}</strong>
        </div>
      </div>

      <Status loading={loading && !data} error={error} />
      {data && (
        <>
          <div className="decision-strip">
            <div>
              <span className="eyebrow">Decision point</span>
              Gate closure {ukDateTime(data.cutoff)} UK
            </div>
            <div>
              <span className="eyebrow">Forecast used</span>
              {latestPub ? (
                <>
                  Published {ukDateTime(latestPub)}
                  {leadMin != null && <span className="muted"> · {Math.floor(leadMin / 60)}h {leadMin % 60}m before gate</span>}
                </>
              ) : "No forecast published before gate closure"}
            </div>
            <div>
              <span className="eyebrow">Lead time</span>
              {horizons.length ? `${Math.min(...horizons).toFixed(0)}–${Math.max(...horizons).toFixed(0)} h ahead` : "—"}
            </div>
          </div>

          <div className="kpis">
            <Kpi label="Forecast wind energy" value={gwh(data.totals.forecast_mwh)} note="Latest forecast at gate closure" />
            <Kpi
              label="P90 wind — plan on at least"
              value={gwh(data.totals.p90_wind_mwh)}
              note={<>Forecast minus the 90th-percentile over-forecast seen {data.band.basis === "trailing" ? "on previous days" : "this month (in-sample)"}</>}
            />
            <Kpi
              label="Typical error range"
              value={`${signedMw(data.band.p10)} … ${signedMw(data.band.p90)}`}
              note={`80% of past D-1 hours fell in this range (n=${data.band.n})`}
            />
            <Kpi
              label="What actually happened"
              value={gwh(data.totals.actual_mwh)}
              note={realised?.n ? <>Mean abs. error {mw(realised.mae)} · bias {signedMw(realised.bias)}</> : "Outturn not available"}
            />
          </div>

          <Panel
            title="Wind generation: plan vs outturn"
            sub="Shaded band = range wind is expected to fall in 80% of the time, from historical day-ahead errors."
            aside={
              <div className="legend">
                <span><Swatch kind="forecast" />D-1 forecast</span>
                <span><Swatch kind="band" />P90–P10 range</span>
                <span><Swatch kind="actual" />Actual (FUELHH)</span>
              </div>
            }
          >
            <div className="chart" style={{ height: 340 }}>
              <ResponsiveContainer>
                <ComposedChart data={rows} margin={{ top: 8, right: 16, bottom: 0, left: 4 }}>
                  <CartesianGrid stroke={c.grid} vertical={false} />
                  <XAxis dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]}
                    tickFormatter={(t) => ukTime(new Date(t).toISOString())} stroke={c.axis} tick={{ fill: c.axis, fontSize: 12 }}
                    ticks={rows.filter((r) => new Date(r.t).getUTCMinutes() === 0 && new Date(r.t).getUTCHours() % 3 === 0).map((r) => r.t)} />
                  <YAxis stroke={c.axis} tick={{ fill: c.axis, fontSize: 12 }} tickFormatter={kfmt} width={44}
                    label={{ value: "MW", angle: -90, position: "insideLeft", fill: c.axis, fontSize: 12 }} />
                  <Tooltip content={<DayTip />} />
                  <Area dataKey="band" stroke="none" fill={c.band} fillOpacity={0.35} connectNulls isAnimationActive={false} />
                  <Line dataKey="forecast" stroke={c.forecast} strokeWidth={2} dot={false} connectNulls isAnimationActive={false} />
                  <Line dataKey="actual" stroke={c.actual} strokeWidth={2} dot={false} connectNulls isAnimationActive={false} />
                  <ReferenceLine y={0} stroke={c.axis} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            <button className="link" onClick={() => setShowTable((s) => !s)}>{showTable ? "Hide" : "Show"} hourly table</button>
            {showTable && <HourTable data={data.forecast} />}
          </Panel>
        </>
      )}
    </>
  );
}

function DayTip({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return (
    <div className="tip">
      <div className="tip-head">{ukTime(new Date(r.t).toISOString())} UK</div>
      {r.forecast != null && <div><Swatch kind="forecast" />Forecast <b>{mw(r.forecast)}</b></div>}
      {r.band && <div><Swatch kind="band" />Range <b>{mw(r.band[0])} – {mw(r.band[1])}</b></div>}
      {r.actual != null && <div><Swatch kind="actual" />Actual <b>{mw(r.actual)}</b></div>}
      {r.actual != null && r.forecast != null && <div className="muted">Error {signedMw(r.forecast - r.actual)}</div>}
    </div>
  );
}

function HourTable({ data }: { data: { time: string; forecast: number; p90_wind: number | null; p10_wind: number | null; actual_at_forecast: number | null; horizon_h: number }[] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr><th>Hour (UK)</th><th>Lead</th><th>Forecast</th><th>P90 wind</th><th>P10 wind</th><th>Actual</th><th>Error</th></tr>
        </thead>
        <tbody>
          {data.map((r) => (
            <tr key={r.time}>
              <td>{ukTime(r.time)}</td>
              <td>{r.horizon_h.toFixed(0)} h</td>
              <td>{mw(r.forecast)}</td>
              <td>{mw(r.p90_wind)}</td>
              <td>{mw(r.p10_wind)}</td>
              <td>{mw(r.actual_at_forecast)}</td>
              <td className={r.actual_at_forecast == null ? "" : r.forecast > r.actual_at_forecast ? "over" : "under"}>
                {r.actual_at_forecast == null ? "—" : signedMw(r.forecast - r.actual_at_forecast)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
