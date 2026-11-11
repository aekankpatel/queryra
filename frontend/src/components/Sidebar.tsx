import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { Dataset, SampleDataset } from "../types";
import { SampleSource } from "./SampleSource";

interface Props {
  datasets: Dataset[];
  selected: string | null;
  onSelect: (id: string) => void;
  onChanged: (select?: string) => void;
  maxUploadMb?: number;
}

export function Sidebar({ datasets, selected, onSelect, onChanged, maxUploadMb }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [over, setOver] = useState(false);
  const [samples, setSamples] = useState<SampleDataset[]>([]);
  const [pick, setPick] = useState("ecommerce");
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.samples().then(setSamples).catch(() => setSamples([]));
  }, []);
  const picked = samples.find((s) => s.id === pick);

  async function upload(file: File) {
    if (maxUploadMb && file.size > maxUploadMb * 1024 * 1024) {
      setError(`That file is ${(file.size / 1048576).toFixed(1)} MB; the limit here is ${maxUploadMb} MB.`);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const ds = await api.upload(file);
      onChanged(ds.id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function sample() {
    setBusy(true);
    setError(null);
    try {
      const ds = await api.loadSample(pick);
      onChanged(ds.id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    if (!confirm("Delete this dataset?")) return;
    await api.deleteDataset(id);
    onChanged();
  }

  return (
    <aside className="sidebar">
      <div className="section-title">Your data</div>
      <div
        className={`dropzone ${over ? "over" : ""}`}
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          const f = e.dataTransfer.files[0];
          if (f) upload(f);
        }}
      >
        {busy ? "Loading…" : (
          <>
            <strong>Upload a file</strong>
            <div className="small">CSV, TSV, Parquet, JSON or XLSX{maxUploadMb ? ` · max ${maxUploadMb} MB` : ""}</div>
          </>
        )}
        <input
          ref={input}
          type="file"
          hidden
          accept=".csv,.tsv,.parquet,.json,.jsonl,.ndjson,.xlsx"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) upload(f);
            e.target.value = "";
          }}
        />
      </div>
      <div className="section-title" style={{ marginTop: 4 }}>Samples</div>
      <div className="row" style={{ gap: 6 }}>
        <select className="sample-select" style={{ flex: 1, minWidth: 0 }} value={pick} aria-label="Sample dataset"
                onChange={(e) => setPick(e.target.value)} disabled={busy}>
          {(samples.length ? samples : [{ id: "ecommerce", name: "E-commerce orders (sample)" }]).map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
        <button className="btn" onClick={sample} disabled={busy}>Load</button>
      </div>
      {picked && (
        <div className="small muted stack" style={{ gap: 2 }}>
          {picked.description && <span>{picked.description}</span>}
          <SampleSource sample={picked} />
        </div>
      )}
      {error && <div className="error-box small">{error}</div>}
      {datasets.length === 0 && <div className="muted small">Nothing here yet.</div>}
      {datasets.map((d) => (
        <div key={d.id} className={`dataset ${selected === d.id ? "active" : ""}`} onClick={() => onSelect(d.id)}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <span className="name">{d.name}</span>
            <button
              className="btn ghost small"
              title="Remove"
              onClick={(e) => {
                e.stopPropagation();
                remove(d.id);
              }}
            >
              ✕
            </button>
          </div>
          <div className="meta">
            {d.row_count.toLocaleString()} rows · {d.column_count} cols · <span className="mono">{d.table}</span>
          </div>
        </div>
      ))}
    </aside>
  );
}
