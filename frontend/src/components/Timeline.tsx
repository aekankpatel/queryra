import { useState } from "react";
import { fmtMs, pretty } from "../format";
import type { TimelineEvent } from "../types";

const COLORS: Record<string, string> = {
  node: "var(--accent)",
  llm: "var(--purple)",
  tool: "var(--ok)",
  decision: "var(--warn)",
  guardrail: "var(--warn)",
  discovery: "var(--muted)",
  error: "var(--err)",
};

const NAMES: Record<string, string> = {
  understand_dataset: "Read the data", profile_dataset: "Profile the columns", mcp_tool_discovery: "Find the tools",
  resolve_time_scope: "Work out the dates", time_scope_resolved: "Dates decided", plan: "Make a plan",
  plan_fallback: "Use a simpler plan", task_contract: "Pin down the question", run_sql: "Run a SQL query",
  sample_rows: "Look at some rows", column_values: "Look at column values", list_tables: "List the tables",
  period_comparison: "Compare two periods", trend_analysis: "Look for a trend", compare_groups: "Compare groups",
  chi_square_test: "Test categories", correlation_analysis: "Check correlations", detect_anomalies: "Look for outliers",
  descriptive_statistics: "Summarise the numbers", create_chart: "Draw a chart", fallback_chart: "Add a chart",
  synthesize: "Write the answer", verify_findings: "Check the numbers", generate_report: "Make the PDF",
  generate_pdf_report: "Write the PDF", replan: "Change the plan", realign_to_question: "Get back on the question",
  revise_answer: "Fix the answer", stop_investigation: "Stop digging", continue_investigation: "Keep digging",
  budget_reached: "Hit the step limit", deadline_reached: "Running out of time, wrap up",
  deadline_exceeded: "Out of time", clarification_needed: "Ask which period",
  duplicate_call_blocked: "Skip a repeated query", tool_not_offered: "Block an unavailable tool",
};
const TYPES: Record<string, string> = {
  node: "step", llm: "AI", tool: "tool", decision: "choice", guardrail: "safety check", discovery: "setup",
};

export function stepName(name: string): string {
  const round = name.match(/^(act|reflect|plan)\s*\(iteration (\d+)\)$/);
  if (round) return `${round[1] === "act" ? "Think" : round[1] === "reflect" ? "Review" : "Plan"} (round ${round[2]})`;
  if (NAMES[name]) return NAMES[name];
  const words = name.replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function Timeline({ events, onEvidence, emptyText }: {
  events: TimelineEvent[]; onEvidence: (id: string) => void; emptyText?: string;
}) {
  const [open, setOpen] = useState<string | null>(null);
  if (!events.length) {
    return <div className="empty small">{emptyText ?? "Each step shows up here as it happens."}</div>;
  }
  return (
    <div className="timeline">
      {events.map((e) => {
        const color = e.status === "error" ? "var(--err)" : COLORS[e.type] ?? "var(--muted)";
        const isOpen = open === e.id;
        return (
          <div key={e.id} className={`tl-item ${isOpen ? "open" : ""}`} onClick={() => setOpen(isOpen ? null : e.id)}>
            <span className={`tl-dot ${e.status === "running" ? "running-dot" : ""}`} style={{ background: color }} />
            <div style={{ minWidth: 0 }}>
              <div className="tl-name" title={e.name}>
                {stepName(e.name)}
                {e.status === "error" && <span className="badge err" style={{ marginLeft: 6 }}>error</span>}
                {e.status === "warning" && <span className="badge warn" style={{ marginLeft: 6 }}>warning</span>}
                {e.origin === "fallback" && (
                  <span className="badge purple" style={{ marginLeft: 6 }} title="Added automatically because no chart was drawn">
                    added automatically
                  </span>
                )}
                {e.origin === "system" && <span className="badge muted" style={{ marginLeft: 6 }}>automatic</span>}
              </div>
              <div className="tl-type">
                {TYPES[e.type] ?? e.type}
                {e.tokens ? ` · ${(e.tokens.input_tokens + e.tokens.output_tokens).toLocaleString()} tokens` : ""}
                {e.evidence_id && (
                  <>
                    {" · "}
                    <span
                      className="ev-chip"
                      onClick={(ev) => {
                        ev.stopPropagation();
                        onEvidence(e.evidence_id!);
                      }}
                    >
                      {e.evidence_id}
                    </span>
                  </>
                )}
              </div>
            </div>
            <span className="tl-dur">{e.status === "running" ? "…" : fmtMs(e.duration_ms)}</span>
            {isOpen && (
              <div className="tl-detail" onClick={(ev) => ev.stopPropagation()}>
                {e.sql && <pre className="code">{e.sql}</pre>}
                {e.input !== undefined && !e.sql && (
                  <>
                    <div className="small muted">input</div>
                    <pre className="code">{pretty(e.input)}</pre>
                  </>
                )}
                {e.error && <div className="error-box small">{e.error}</div>}
                {e.output !== undefined && (
                  <>
                    <div className="small muted">output</div>
                    <pre className="code">{pretty(e.output)}</pre>
                  </>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
