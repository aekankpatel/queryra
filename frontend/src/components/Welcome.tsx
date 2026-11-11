import { useEffect, useState } from "react";
import { api } from "../api";
import type { Health, SampleDataset } from "../types";
import { ReplayList } from "./ReplayView";

const STEPS = [
  ["Pick some data", "Upload a spreadsheet or use one of the samples."],
  ["Ask a question", "In plain words, like “Why did sales drop last quarter?”"],
  ["See how it works it out", "Every query and calculation shows up as it happens."],
  ["Get an answer you can check", "Each number is checked against the data. Charts and a PDF are included."],
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
  const canLoad = !busy && !!health && !health.storage_error;
  return (
    <div className="stack" style={{ maxWidth: 860 }}>
      <div className="card hero">
        <h1>Ask your data a question.</h1>
        <p>
          Queryra looks through your data the way an analyst would. It runs the numbers, checks its own work and
          gives you a short answer with charts.
        </p>
        <div className="row" style={{ marginTop: 16 }}>
          <button className="btn primary" disabled={!canLoad} onClick={() => load()}>
            {busy ? "Loading…" : "Try it with sample shop data"}
          </button>
          <span className="small muted">
            or upload your own file on the left{health?.limits ? ` (up to ${health.limits.max_upload_mb} MB)` : ""}.
          </span>
        </div>
        {samples.length > 1 && (
          <div className="row" style={{ marginTop: 10, gap: 6 }}>
            <span className="small muted">Other samples:</span>
            {samples.filter((x) => x.id !== "ecommerce").map((x) => (
              <button key={x.id} className="btn small" title={x.description ?? ""} disabled={!canLoad}
                      onClick={() => load(x.id)}>
                {x.name}
              </button>
            ))}
          </div>
        )}
        {error && <div className="error-box small" style={{ marginTop: 10 }}>{error}</div>}
      </div>
      <div className="steps">
        {STEPS.map(([t, d]) => (
          <div key={t} className="step">
            <strong>{t}</strong>
            <span className="small muted">{d}</span>
          </div>
        ))}
      </div>
      {(health?.replays ?? 0) > 0 && (
        <div className="stack" style={{ marginTop: 8 }}>
          <h3 style={{ margin: 0, fontFamily: "var(--serif)", fontSize: 18 }}>Or watch an example</h3>
          <div className="small muted">Real questions answered earlier, replayed step by step.</div>
          <ReplayList onOpen={onReplay} />
        </div>
      )}
    </div>
  );
}
