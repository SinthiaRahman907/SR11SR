const UK = "Europe/London";

export const mw = (v: number | null | undefined, digits = 0) =>
  v == null ? "—" : `${v.toLocaleString("en-GB", { maximumFractionDigits: digits })} MW`;

export const signedMw = (v: number | null | undefined) =>
  v == null ? "—" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toLocaleString("en-GB", { maximumFractionDigits: 0 })} MW`;

export const gwh = (mwh: number | null | undefined) =>
  mwh == null ? "—" : `${(mwh / 1000).toLocaleString("en-GB", { maximumFractionDigits: 1 })} GWh`;

export const pct = (v: number | null | undefined, digits = 1) =>
  v == null ? "—" : `${v.toFixed(digits)}%`;

export const ukTime = (iso: string) =>
  new Date(iso).toLocaleTimeString("en-GB", { timeZone: UK, hour: "2-digit", minute: "2-digit" });

export const ukDateTime = (iso: string) =>
  new Date(iso).toLocaleString("en-GB", {
    timeZone: UK, weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
  });

export const ukDay = (iso: string) =>
  new Date(iso).toLocaleDateString("en-GB", { timeZone: UK, day: "numeric", month: "short" });

export const longDay = (isoDate: string) =>
  new Date(`${isoDate}T12:00:00Z`).toLocaleDateString("en-GB", {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  });

export const addDays = (isoDate: string, n: number) => {
  const d = new Date(`${isoDate}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
};

export const kfmt = (v: number) => (Math.abs(v) >= 1000 ? `${(v / 1000).toFixed(v % 1000 ? 1 : 0)}k` : `${v}`);
