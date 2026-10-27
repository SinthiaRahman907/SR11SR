import { useMemo, useState } from "react";
import {
  Area, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Line, LineChart, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api, Meta } from "./api";
import { usePalette } from "./colors";
import { kfmt, mw, pct, signedMw, ukDateTime, ukDay } from "./format";
import { Kpi, Panel, Status, Swatch, useAsync } from "./ui";

type Mode = "dayahead" | "horizon";
const AX = (c: { axis: string }) => ({ stroke: c.axis, tick: { fill: c.axis, fontSize: 12 } });

export default function Accuracy({ meta, gate }: { meta: Meta; gate: string }) {
  const [mode, setMode] = useState<Mode>("dayahead");
  const [horizon, setHorizon] = useState(24);
  const acc = useAsync(() => api.accuracy(mode, gate, horizon), [mode, gate, horizon]);
  const curve = useAsync(() => api.horizonCurve(), []);
  const c = usePalette();
  const s = acc.data?.summary;

  const series = useMemo(() => acc.data?.series.map((r) => ({ ...r, t: Date.parse(r.time) })) ?? [], [acc.data]);
  const curvePts = useMemo(
    () => curve.data?.points.filter((p) => p.n > 0).map((p) => ({ ...p, band: [p.p10, p.p90] as [number | null, number | null] })) ?? [],
    [curve.data],
  );

  return (
    <>
      <div className="toolbar">
        <div className="segmented" role="tablist">
          <button role="tab" aria-selected={mode === "dayahead"} className={mode === "dayahead" ? "on" : ""} onClick={() => setMode("dayahead")}>
            As used at gate closure (D-1 {gate})
          </button>
          <button role="tab" aria-selected={mode === "horizon"} className={mode === "horizon" ? "on" : ""} onClick={() => setMode("horizon")}>
            Fixed lead time
          </button>
        </div>
        {mode === "horizon" && (
          <label className="slider">
            Lead time <b>{horizon} h</b>
            <input type="range" min={0} max={meta.max_horizon_h} step={1} value={horizon} onChange={(e) => setHorizon(+e.target.value)} />
          </label>
        )}
        <div className="toolbar-title">
          <span className="eyebrow">Evaluation window</span>
          <strong>Delivery {ukDay(meta.first_delivery_day)} – {ukDay(meta.last_delivery_day)} 2026</strong>
        </div>
      </div>

      <Status loading={acc.loading && !acc.data} error={acc.error} />

      {s && s.n > 0 && (
        <>
          <p className="headline">
            {mode === "dayahead" ? "When the desk bought power, " : `With ${horizon} h of lead time, `}
            the wind forecast was off by <b>{mw(s.mae)}</b> on average — <b>{pct(s.nmae_pct)}</b> of mean wind output.
            80% of hours landed between <b>{signedMw(s.p10)}</b> and <b>{signedMw(s.p90)}</b>
            {s.bias != null && Math.abs(s.bias) > 50 && (
              <>, with a systematic <b>{s.bias > 0 ? "over" : "under"}-forecast</b> of {mw(Math.abs(s.bias))}</>
            )}.
          </p>

          <div className="kpis">
            <Kpi label="Mean absolute error" value={mw(s.mae)} note={`nMAE ${pct(s.nmae_pct)} · RMSE ${mw(s.rmse)}`} />
            <Kpi label="Bias (forecast − actual)" value={signedMw(s.bias)} tone={s.bias! > 0 ? "over" : "under"}
              note={`${pct(s.pct_over, 0)} of hours over-forecast`} />
            <Kpi label="P10 … P90 error" value={`${signedMw(s.p10)} … ${signedMw(s.p90)}`} note="Central 80% of hourly errors" />
            <Kpi label="Worst hours" value={`${signedMw(s.max_under)} / ${signedMw(s.max_over)}`}
              note={`n=${s.n} hours · mean lead ${s.mean_horizon_h?.toFixed(1)} h`} />
          </div>

          <div className="grid-2">
            <Panel title="Error grows with lead time"
              sub="Mean absolute error and the P10–P90 error range by forecast lead time. The D-1 decision sits around 14–38 h."
              aside={<div className="legend"><span><Swatch kind="forecast" />MAE</span><span><Swatch kind="band" />P10–P90</span></div>}>
              <div className="chart" style={{ height: 260 }}>
                <ResponsiveContainer>
                  <ComposedChart data={curvePts} margin={{ top: 22, right: 12, bottom: 4, left: 4 }}>
                    <CartesianGrid stroke={c.grid} vertical={false} />
                    <XAxis dataKey="horizon_h" type="number" domain={[0, meta.max_horizon_h]} ticks={[0, 6, 12, 18, 24, 30, 36, 42, 48]} {...AX(c)}
                      label={{ value: "lead time (h)", position: "insideBottomRight", offset: -2, fill: c.axis, fontSize: 12 }} />
                    <YAxis tickFormatter={kfmt} width={44} {...AX(c)} />
                    <Tooltip content={<CurveTip />} />
                    <Area dataKey="band" stroke="none" fill={c.band} fillOpacity={0.35} isAnimationActive={false} />
                    <Line dataKey="mae" stroke={c.forecast} strokeWidth={2} dot={false} isAnimationActive={false} />
                    <ReferenceLine y={0} stroke={c.axis} />
                    {mode === "horizon" && <ReferenceLine x={horizon} stroke={c.ink} strokeDasharray="3 3" />}
                    {mode === "dayahead" && s.mean_horizon_h != null && (
                      <ReferenceLine x={s.mean_horizon_h} stroke={c.ink} strokeDasharray="3 3"
                        label={{ value: "D-1 avg", position: "top", fill: c.ink, fontSize: 11 }} />
                    )}
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </Panel>

            <Panel title="Error distribution" sub="Share of hours by error size. Right of zero = over-forecast (desk ends up short of wind)."
              aside={<div className="legend"><span><Swatch kind="under" />Under</span><span><Swatch kind="over" />Over</span></div>}>
              <div className="chart" style={{ height: 260 }}>
                <ResponsiveContainer>
                  <BarChart data={acc.data!.histogram} margin={{ top: 8, right: 12, bottom: 4, left: 4 }} barCategoryGap={2}>
                    <CartesianGrid stroke={c.grid} vertical={false} />
                    <XAxis dataKey="from" tickFormatter={kfmt} {...AX(c)} />
                    <YAxis tickFormatter={(v) => `${v}%`} width={40} {...AX(c)} />
                    <Tooltip content={<HistTip />} cursor={{ fill: c.grid }} />
                    <Bar dataKey="pct" radius={[4, 4, 0, 0]} isAnimationActive={false}>
                      {acc.data!.histogram.map((b) => <Cell key={b.from} fill={b.from >= 0 ? c.over : c.under} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Panel>
          </div>

          <Panel title="Forecast vs actual, whole window"
            sub={mode === "dayahead" ? "Each hour shows the forecast that was available at gate closure the day before." : `Each hour shows the latest forecast published at least ${horizon} h earlier.`}
            aside={<div className="legend"><span><Swatch kind="forecast" />Forecast</span><span><Swatch kind="actual" />Actual</span></div>}>
            <div className="chart" style={{ height: 300 }}>
              <ResponsiveContainer>
                <LineChart data={series} margin={{ top: 8, right: 16, bottom: 0, left: 4 }}>
                  <CartesianGrid stroke={c.grid} vertical={false} />
                  <XAxis dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]}
                    tickFormatter={(t) => ukDay(new Date(t).toISOString())} minTickGap={40} {...AX(c)} />
                  <YAxis tickFormatter={kfmt} width={44} {...AX(c)} />
                  <Tooltip content={<SeriesTip />} />
                  <Line dataKey="forecast" stroke={c.forecast} strokeWidth={1.5} dot={false} isAnimationActive={false} />
                  <Line dataKey="actual" stroke={c.actual} strokeWidth={1.5} dot={false} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Panel>

          <div className="grid-2">
            <Panel title="Error by hour of day" sub="MAE per delivery hour (UK). Helps target which blocks to hedge.">
              <div className="chart" style={{ height: 240 }}>
                <ResponsiveContainer>
                  <BarChart data={acc.data!.by_hour} margin={{ top: 8, right: 12, bottom: 4, left: 4 }} barCategoryGap={2}>
                    <CartesianGrid stroke={c.grid} vertical={false} />
                    <XAxis dataKey="hour" tickFormatter={(h) => `${String(h).padStart(2, "0")}`} {...AX(c)} />
                    <YAxis tickFormatter={kfmt} width={44} {...AX(c)} />
                    <Tooltip content={<HourTip />} cursor={{ fill: c.grid }} />
                    <Bar dataKey="mae" fill={c.forecast} radius={[4, 4, 0, 0]} isAnimationActive={false} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Panel>
            <Panel title="Error by delivery day" sub="Daily MAE — spot the days that hurt, then open them in the Day-ahead view.">
              <div className="chart" style={{ height: 240 }}>
                <ResponsiveContainer>
                  <BarChart data={acc.data!.by_day} margin={{ top: 8, right: 12, bottom: 4, left: 4 }} barCategoryGap={2}>
                    <CartesianGrid stroke={c.grid} vertical={false} />
                    <XAxis dataKey="day" tickFormatter={(d) => ukDay(d)} minTickGap={24} {...AX(c)} />
                    <YAxis tickFormatter={kfmt} width={44} {...AX(c)} />
                    <Tooltip content={<DailyTip />} cursor={{ fill: c.grid }} />
                    <Bar dataKey="mae" fill={c.forecast} radius={[4, 4, 0, 0]} isAnimationActive={false} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Panel>
          </div>
        </>
      )}
      {s && s.n === 0 && <div className="status">No forecast/actual pairs for this setting.</div>}
    </>
  );
}

type TipProps<T> = { active?: boolean; payload?: { payload: T }[] };

function CurveTip({ active, payload }: TipProps<{ horizon_h: number; mae: number; p10: number; p90: number; n: number }>) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return <div className="tip"><div className="tip-head">{p.horizon_h} h lead</div>
    <div>MAE <b>{mw(p.mae)}</b></div><div>P10…P90 <b>{signedMw(p.p10)} … {signedMw(p.p90)}</b></div>
    <div className="muted">n={p.n}</div></div>;
}
function HistTip({ active, payload }: TipProps<{ from: number; to: number; count: number; pct: number }>) {
  if (!active || !payload?.length) return null;
  const b = payload[0].payload;
  return <div className="tip"><div className="tip-head">{signedMw(b.from)} to {signedMw(b.to)}</div>
    <div><b>{pct(b.pct)}</b> of hours ({b.count})</div></div>;
}
function SeriesTip({ active, payload }: TipProps<{ time: string; actual: number; forecast: number; error: number; publishTime: string }>) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return <div className="tip"><div className="tip-head">{ukDateTime(r.time)}</div>
    <div><Swatch kind="forecast" />Forecast <b>{mw(r.forecast)}</b></div>
    <div><Swatch kind="actual" />Actual <b>{mw(r.actual)}</b></div>
    <div>Error <b>{signedMw(r.error)}</b></div>
    <div className="muted">Published {ukDateTime(r.publishTime)}</div></div>;
}
function HourTip({ active, payload }: TipProps<{ hour: number; mae: number; bias: number; n: number }>) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return <div className="tip"><div className="tip-head">{String(r.hour).padStart(2, "0")}:00 UK</div>
    <div>MAE <b>{mw(r.mae)}</b></div><div>Bias <b>{signedMw(r.bias)}</b></div><div className="muted">n={r.n}</div></div>;
}
function DailyTip({ active, payload }: TipProps<{ day: string; mae: number; bias: number; mean_actual: number }>) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return <div className="tip"><div className="tip-head">{ukDay(r.day)}</div>
    <div>MAE <b>{mw(r.mae)}</b></div><div>Bias <b>{signedMw(r.bias)}</b></div>
    <div className="muted">Mean wind {mw(r.mean_actual)}</div></div>;
}
