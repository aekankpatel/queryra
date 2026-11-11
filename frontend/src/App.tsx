import { useCallback, useEffect, useState } from "react";
import { accessCode, api, ApiError, setAccessCode } from "./api";
import { AnalyzeView } from "./components/AnalyzeView";
import { DataView } from "./components/DataView";
import { EvalsView } from "./components/EvalsView";
import { Sidebar } from "./components/Sidebar";
import { ToolsView } from "./components/ToolsView";
import { ReplayList, ReplayView } from "./components/ReplayView";
import { Welcome } from "./components/Welcome";
import { CONTACT_URL } from "./links";
import type { Dataset, Health } from "./types";

type Tab = "analyze" | "replays" | "data" | "tools" | "evals";
const TABS: [Tab, string][] = [["analyze", "Ask"], ["replays", "Examples"], ["data", "Data"], ["tools", "Tools"],
  ["evals", "Tests"]];
const REPO_URL = import.meta.env.VITE_REPO_URL ?? "https://github.com/aekankpatel/queryra";

export default function App() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("analyze");
  const [health, setHealth] = useState<Health | null>(null);
  const [connecting, setConnecting] = useState(true);
  const [offline, setOffline] = useState(false);
  const [left, setLeft] = useState<number | null>(null);
  const [replayId, setReplayId] = useState<string | null>(null);
  const openReplay = (id: string) => {
    setReplayId(id);
    setTab("replays");
  };

  const refresh = useCallback(async (select?: string) => {
    try {
      const list = await api.datasets();
      setDatasets(list);
      setOffline(false);
      setSelected((cur) => select ?? (cur && list.some((d) => d.id === cur) ? cur : list[0]?.id ?? null));
    } catch (e) {
      if (e instanceof ApiError && e.status === 0) setOffline(true);
    }
  }, []);

  // A free-tier backend may be asleep: keep retrying for ~2 minutes before showing "offline".
  useEffect(() => {
    let cancelled = false;
    (async () => {
      for (let attempt = 0; attempt < 12 && !cancelled; attempt++) {
        try {
          const h = await api.health();
          if (cancelled) return;
          setHealth(h);
          setConnecting(false);
          setOffline(false);
          refresh();
          api.usage().then((u) => setLeft(u.approx_analyses_left)).catch(() => undefined);
          return;
        } catch {
          await new Promise((r) => setTimeout(r, Math.min(15000, 2000 * (attempt + 1))));
        }
      }
      if (!cancelled) {
        setConnecting(false);
        setOffline(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refresh]);

  const dataset = datasets.find((d) => d.id === selected) ?? null;
  const needsDataset = tab === "analyze" || tab === "data";

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand"><img src="/beacon.svg" alt="" />Queryra</div>
        <nav className="tabs" aria-label="Sections">
          {TABS.map(([id, label]) => (
            <button key={id} className={`tab ${tab === id ? "active" : ""}`} aria-current={tab === id ? "page" : undefined}
              onClick={() => setTab(id)}>{label}</button>
          ))}
        </nav>
        <div className="spacer" />
        {left !== null && health?.public_mode && !health.replay_only && (
          <span className="small muted" title="Everyone shares a small free allowance each day">
            {left > 0 ? `About ${left} questions left today` : "No questions left today"}
          </span>
        )}
        {offline && <span className="badge err">Offline</span>}
      </header>
      <div className="layout">
        <Sidebar datasets={datasets} selected={selected} onSelect={setSelected} onChanged={refresh}
          maxUploadMb={health?.limits?.max_upload_mb} />
        <main className="main">
          {connecting && (
            <div className="card" role="status" style={{ marginBottom: 14 }}>
              <strong>Waking up the server…</strong>
              <div className="small muted">It sleeps when nobody is using it, so the first visit can take up to a minute.</div>
            </div>
          )}
          {health?.storage_error && (
            <div className="error-box small" role="alert" style={{ marginBottom: 14 }}>
              <strong>Saving data isn't working right now.</strong> The examples still work. Uploads and questions
              are paused until it's fixed. <span className="muted">({health.storage_error})</span>
            </div>
          )}
          {offline && !connecting && (
            <div className="error-box small" style={{ marginBottom: 14 }}>
              Can't reach the server right now. Please try again in a few minutes.
            </div>
          )}
          {health?.public_mode && <DemoNotice health={health} />}
          {health && !health.llm.configured && tab === "analyze" && (
            <div className="error-box small" style={{ marginBottom: 14, background: "var(--warn-soft)", color: "var(--warn)" }}>
              The AI isn't set up on this server yet (no key for “{health.llm.provider}”). The examples still work.
            </div>
          )}
          {health?.replay_only && tab === "analyze" && (
            <div className="card small" style={{ marginBottom: 14 }}>
              Live questions are turned off for now. You can still watch the examples below.
            </div>
          )}
          {tab === "replays" ? (
            replayId ? <ReplayView id={replayId} onBack={() => setReplayId(null)} />
              : (
                <div className="stack">
                  <div className="card small">
                    These are real questions answered earlier and saved. You can replay them step by step at any
                    time, and they don't count towards the daily limit.
                  </div>
                  <ReplayList onOpen={openReplay} />
                </div>
              )
          ) : needsDataset && !dataset ? (
            <Welcome health={health} onReplay={openReplay} onSample={async (id?: string) => {
              const ds = await api.loadSample(id);
              await refresh(ds.id);
              setTab("analyze");
            }} />
          ) : tab === "analyze" && dataset ? (
            <AnalyzeView dataset={dataset} />
          ) : tab === "data" && dataset ? (
            <DataView dataset={dataset} />
          ) : tab === "tools" ? (
            <ToolsView />
          ) : (
            <EvalsView />
          )}
          <footer className="footer small muted">
            Queryra, made by Aekank Patel ·{" "}
            <a href={REPO_URL} target="_blank" rel="noreferrer">Code on GitHub</a> ·{" "}
            <a href={CONTACT_URL} target="_blank" rel="noreferrer">Contact</a>
            {health?.llm.configured && <> · AI by {health.llm.provider === "cloudflare" ? "Cloudflare" : health.llm.provider}</>}
          </footer>
        </main>
      </div>
    </div>
  );
}

function DemoNotice({ health }: { health: Health }) {
  const [code, setCode] = useState(accessCode());
  const [saved, setSaved] = useState(Boolean(accessCode()));
  const l = health.limits;
  return (
    <div className="notice" style={{ marginBottom: 22 }}>
      <strong>This is a free demo.</strong>{" "}
      {l && <>
        Files up to {l.max_upload_mb} MB. Only you can see your data, and it's deleted after{" "}
        {l.data_ttl_hours > 0 ? `${l.data_ttl_hours} hours` : "a while"}.
      </>}{" "}
      Please don't upload anything private.
      {health.access_code_required && !health.replay_only && (
        <div className="row code-row" style={{ marginTop: 8 }}>
          <label htmlFor="code">Asking your own questions needs an access code:</label>
          <input id="code" type="password" value={code} placeholder="Access code" autoComplete="off"
            onChange={(e) => { setCode(e.target.value); setSaved(false); }} />
          <button className="btn small" onClick={() => { setAccessCode(code.trim()); setSaved(true); }}>Save</button>
          {saved && code && <span className="badge ok">Saved</span>}
          <span className="muted">
            Don't have one? <a href={CONTACT_URL} target="_blank" rel="noreferrer">Contact me</a>.
          </span>
        </div>
      )}
    </div>
  );
}
