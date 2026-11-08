import { useEffect, useState } from "react";
import { api } from "../api";
import type { Health, SampleDataset } from "../types";
import { ReplayList } from "./ReplayView";

const STEPS = [
  ["Understand", "Profiles your data: column roles, missing values, outliers, correlations."],
  ["Investigate", "Plans hypotheses, discovers tools over MCP and runs read-only SQL and statistical tests."],
  ["Verify", "Checks every number against tool outputs, and the answer against the question's period, metric and grouping."],
  ["Report", "Interactive charts, a full execution timeline and a downloadable PDF."],
];

export function Welcome({ health, onSample, onReplay }: {
  health: Health | null; onSample: (id?: string) => Promise<void>; onReplay: (id: string) => void;
}) {
  const [samples, setSamples] = useState<SampleDataset[]>([]);
  useEffect(() => {
    api.samples().then(setSamples).catch(() => setSamples([]));
  }, []);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function load(id?: string) {
    setBusy(true);
    setError(null);
    try {
      await onSample(id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="stack" style={{ maxWidth: 860 }}>
      <div className="card">
        <h1 style={{ margin: "0 0 6px", fontSize: 26, letterSpacing: "-0.02em" }}>Ask your data why.</h1>
        <p style={{ margin: 0, fontSize: 15 }}>
          Queryra is an autonomous data analyst. Upload a dataset, ask a business question in plain English, and watch
          the agent plan, query, test and verify its way to an evidence-backed answer.
        </p>
        <div className="row" style={{ marginTop: 14 }}>
          <button className="btn primary" disabled={busy || !health || health.replay_only} onClick={() => load()}>
            {busy ? "Loading sample…" : "Try it with sample e-commerce data"}
          </button>
          <span className="small muted">
            or upload a CSV, TSV, Parquet, JSON or XLSX file from the sidebar
            {health?.limits ? ` (up to ${health.limits.max_upload_mb} MB)` : ""}.
          </span>
        </div>
        {samples.length > 1 && (
          <div className="row" style={{ marginTop: 10, flexWrap: "wrap", gap: 6 }}>
            <span className="small muted">More sample datasets:</span>
            {samples.filter((x) => x.id !== "ecommerce").map((x) => (
              <button key={x.id} className="btn small" title={`${x.description ?? ""} Source: ${x.source ?? "-"} (${x.license ?? "-"})`}
                      disabled={busy || !health || health.replay_only} onClick={() => load(x.id)}>
                {x.name}
              </button>
            ))}
          </div>
        )}
        {error && <div className="error-box small" style={{ marginTop: 10 }}>{error}</div>}
      </div>
      <div className="metrics">
        {STEPS.map(([t, d], i) => (
          <div key={t} className="metric">
            <div className="label">{i + 1}. {t}</div>
            <div className="small" style={{ marginTop: 4 }}>{d}</div>
          </div>
        ))}
      </div>
      <p className="small muted">
        Try asking: “Why did our revenue decline last quarter, and which customer segments contributed most?”
      </p>
      {(health?.replays ?? 0) > 0 && (
        <div className="stack">
          <h3 style={{ margin: "8px 0 0" }}>Or watch a recorded investigation</h3>
          <div className="small muted">Real runs on Cloudflare Workers AI, replayed step by step. No AI budget used.</div>
          <ReplayList onOpen={onReplay} />
        </div>
      )}
    </div>
  );
}
