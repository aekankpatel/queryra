import { useEffect, useRef } from "react";
import Plotly from "plotly.js-dist-min";
import type { Chart } from "../types";

const dark = () => window.matchMedia?.("(prefers-color-scheme: dark)").matches;

// charts saved before the redesign use the old palette: show them in the current one
const OLD = ["#2563eb", "#f97316", "#10b981", "#a855f7", "#ef4444", "#14b8a6", "#eab308", "#64748b"];
const PALETTE = ["#1f5fbf", "#d9822b", "#2f8a57", "#7a5bb8", "#c4403a", "#2b8c8c", "#b8962e", "#77746e"];
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
      font: { family: "system-ui, sans-serif", color: isDark ? "#ececea" : "#1b1b1a", size: 12 },
      colorway: PALETTE,
      xaxis: { ...((chart.figure.layout as any)?.xaxis ?? {}), gridcolor: isDark ? "#2b2b2b" : "#e6e6e3" },
      yaxis: { ...((chart.figure.layout as any)?.yaxis ?? {}), gridcolor: isDark ? "#2b2b2b" : "#e6e6e3" },
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
