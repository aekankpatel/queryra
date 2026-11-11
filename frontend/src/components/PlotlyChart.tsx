import { useEffect, useRef } from "react";
import Plotly from "plotly.js-dist-min";
import type { Chart } from "../types";

const dark = () => window.matchMedia?.("(prefers-color-scheme: dark)").matches;

// charts saved before the redesign use the old palette: show them in the current one
const OLD = ["#2563eb", "#f97316", "#10b981", "#a855f7", "#ef4444", "#14b8a6", "#eab308", "#64748b"];  // original
const PALETTE = ["#b44d6c", "#6f9a7e", "#d9a35c", "#5f6b8a", "#c97a5a", "#8a6f9e", "#4f8c8f", "#9a8f88"];
const recolor = (v: unknown): unknown => {
  if (typeof v === "string") {
    const i = OLD.indexOf(v.toLowerCase());
    return i >= 0 ? PALETTE[i] : v;
  }
  if (Array.isArray(v)) return v.map(recolor);
  if (v && typeof v === "object") return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, recolor(x)]));
  return v;
};

export function PlotlyChart({ chart, height = 340 }: { chart: Chart; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const isDark = dark();
    const layout = {
      ...(chart.figure.layout as object),
      height,
      autosize: true,
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      font: { family: "system-ui, sans-serif", color: isDark ? "#f1e9ec" : "#2d2a2e", size: 12 },
      colorway: PALETTE,
      xaxis: { ...((chart.figure.layout as any)?.xaxis ?? {}), gridcolor: isDark ? "#3a3237" : "#ece2e4" },
      yaxis: { ...((chart.figure.layout as any)?.yaxis ?? {}), gridcolor: isDark ? "#3a3237" : "#ece2e4" },
      template: undefined,
    };
    Plotly.react(ref.current, recolor(chart.figure.data) as Plotly.Data[], layout as Partial<Plotly.Layout>, {
      responsive: true,
      displaylogo: false,
    });
    const el = ref.current;
    return () => {
      Plotly.purge(el);
    };
  }, [chart, height]);
  return <div ref={ref} className="chart-box" />;
}
