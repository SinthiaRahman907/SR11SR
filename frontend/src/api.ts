// Typed client for the FastAPI backend. Same-origin in prod; proxied in dev.

export interface Summary {
  n: number;
  mae?: number;
  rmse?: number;
  bias?: number;
  nmae_pct?: number | null;
  mean_actual?: number;
  median_abs?: number;
  p90_abs?: number;
  p10?: number;
  p50?: number;
  p90?: number;
  max_over?: number;
  max_under?: number;
  pct_over?: number;
  mean_horizon_h?: number;
}

export interface Meta {
  source: string;
  loaded_at: string | null;
  first_delivery_day: string;
  last_delivery_day: string;
  default_gate: string;
  max_horizon_h: number;
  n_actuals: number;
  n_forecast_targets: number;
  n_forecast_points: number;
  n_publications: number;
  first_publication: string | null;
  last_publication: string | null;
}

export interface DayForecastRow {
  time: string;
  forecast: number;
  publishTime: string;
  horizon_h: number;
  p90_wind: number | null;
  p10_wind: number | null;
  actual_at_forecast: number | null;
}

export interface DayView {
  day: string;
  cutoff: string;
  forecast_publish_times: string[];
  band: { p10: number | null; p50: number | null; p90: number | null; n: number; basis: string };
  forecast: DayForecastRow[];
  actual: { time: string; actual: number }[];
  totals: { forecast_mwh: number; p90_wind_mwh: number | null; actual_mwh: number | null };
  realised: Summary;
}

export interface Accuracy {
  mode: "dayahead" | "horizon";
  gate: string;
  horizon_h: number;
  summary: Summary;
  by_hour: { hour: number; n: number; mae: number; bias: number; p10: number; p90: number }[];
  by_day: { day: string; n: number; mae: number; bias: number; mean_actual: number }[];
  histogram: { from: number; to: number; count: number; pct: number }[];
  series: { time: string; actual: number; forecast: number; error: number; publishTime: string; horizon_h: number }[];
}

export interface HorizonPoint {
  horizon_h: number;
  n: number;
  mae: number | null;
  rmse: number | null;
  bias: number | null;
  p10: number | null;
  p90: number | null;
  nmae_pct: number | null;
}

async function get<T>(path: string, params: Record<string, string | number> = {}): Promise<T> {
  const qs = new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)]));
  const res = await fetch(`/api/${path}${qs.size ? `?${qs}` : ""}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `${res.status} ${res.statusText}`);
  }
  return res.json();
}

export const api = {
  meta: () => get<Meta>("meta"),
  day: (date: string, gate: string) => get<DayView>("day", { date, gate }),
  accuracy: (mode: string, gate: string, horizon: number) =>
    get<Accuracy>("accuracy", { mode, gate, horizon }),
  horizonCurve: () => get<{ points: HorizonPoint[] }>("horizon-curve", { step: 2 }),
};
