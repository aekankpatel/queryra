import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { Dataset, SampleDataset } from "../types";

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
  const [loading, setLoading] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.samples().then(setSamples).catch(() => setSamples([]));
  }, []);

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

  async function sample(id: string) {
    setBusy(true);
    setLoading(id);
    setError(null);
    try {
      const ds = await api.loadSample(id);
      onChanged(ds.id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      setLoading(null);
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
        {busy && !loading ? "Uploading…" : (
          <>
            <span className="link">Upload a file</span>
            <div className="small muted">CSV, Excel, Parquet or JSON{maxUploadMb ? `, up to ${maxUploadMb} MB` : ""}</div>
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
            {d.row_count.toLocaleString()} rows, {d.column_count} columns
          </div>
        </div>
      ))}
      <div className="section-title" style={{ marginTop: 12 }}>Or try a sample</div>
      <ul className="sample-list">
        {(samples.length ? samples : [{ id: "ecommerce", name: "E-commerce orders (sample)" } as SampleDataset]).map((x) => (
          <li key={x.id}>
            <button disabled={busy} onClick={() => sample(x.id)} title={x.description ?? ""}>
              {loading === x.id ? "Loading…" : x.name.replace(" (sample)", "")}
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}
