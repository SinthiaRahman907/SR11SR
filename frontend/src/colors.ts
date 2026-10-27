import { useEffect, useState } from "react";

// SVG presentation attributes can't use CSS var(), so resolve the theme
// tokens once and re-resolve when the OS colour scheme flips.
const TOKENS = ["actual", "forecast", "band", "over", "under", "grid", "axis", "ink", "surface"] as const;
export type Palette = Record<(typeof TOKENS)[number], string>;

function read(): Palette {
  const cs = getComputedStyle(document.documentElement);
  return Object.fromEntries(TOKENS.map((t) => [t, cs.getPropertyValue(`--c-${t}`).trim()])) as Palette;
}

export function usePalette(): Palette {
  const [p, setP] = useState<Palette>(read);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const on = () => setP(read());
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return p;
}
