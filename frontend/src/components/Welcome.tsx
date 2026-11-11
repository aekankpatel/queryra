import { useState } from "react";
import type { Health } from "../types";
import { ReplayList } from "./ReplayView";

export function Welcome({ health, onSample, onReplay }: {
  health: Health | null; onSample: (id?: string) => Promise<void>; onReplay: (id: string) => void;
}) {
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
    <div className="welcome">
      <h1>Ask your data a <span className="mark">question</span></h1>
      <p>
        Upload a spreadsheet and ask something in plain English, like “why did sales drop last quarter?”.
        Queryra works it out step by step. You can see every query it runs, and every number in the answer is
        checked against your data.
      </p>
      <div className="row" style={{ marginTop: 18 }}>
        <button className="btn primary" disabled={!canLoad} onClick={() => load()}>
          {busy ? "Loading…" : "Try it with sample shop data"}
        </button>
        <span className="small muted">or pick a file or another sample on the left.</span>
      </div>
      {error && <div className="error-box small" style={{ marginTop: 10 }}>{error}</div>}
      {(health?.replays ?? 0) > 0 && (
        <>
          <h2>Or watch an example</h2>
          <p className="small muted" style={{ marginTop: 0 }}>Questions answered earlier. Watching them is free.</p>
          <ReplayList onOpen={onReplay} />
        </>
      )}
    </div>
  );
}
