import { ReactNode, useEffect, useState } from "react";

/** Minimal async hook: re-runs when deps change, ignores stale responses. */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [state, setState] = useState<{ data?: T; error?: string; loading: boolean }>({ loading: true });
  useEffect(() => {
    let live = true;
    setState((s) => ({ ...s, loading: true, error: undefined }));
    fn().then(
      (data) => live && setState({ data, loading: false }),
      (e: Error) => live && setState({ error: e.message, loading: false }),
    );
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}

export function Kpi({ label, value, note, tone }: { label: string; value: string; note?: ReactNode; tone?: "over" | "under" }) {
  return (
    <div className="kpi">
      <div className="kpi-label">{label}</div>
      <div className={`kpi-value ${tone ?? ""}`}>{value}</div>
      {note && <div className="kpi-note">{note}</div>}
    </div>
  );
}

export function Panel({ title, sub, children, aside }: { title: string; sub?: ReactNode; children: ReactNode; aside?: ReactNode }) {
  return (
    <section className="panel">
      <header className="panel-head">
        <div>
          <h3>{title}</h3>
          {sub && <p className="panel-sub">{sub}</p>}
        </div>
        {aside}
      </header>
      {children}
    </section>
  );
}

export function Status({ loading, error }: { loading: boolean; error?: string }) {
  if (error) return <div className="status error">Couldn’t load data: {error}</div>;
  if (loading) return <div className="status">Loading Elexon data…</div>;
  return null;
}

export function Swatch({ kind }: { kind: "actual" | "forecast" | "band" | "over" | "under" }) {
  return <span className={`swatch ${kind}`} aria-hidden />;
}
