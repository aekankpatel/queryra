"""Retrospective rescoring of recorded runs: no LLM calls, no neurons.

    python -m evals.rescore --runs-db <runs.sqlite> --datasets-dir <dir> \
        --run CASE=RUN_ID [--run ...] --out <file.json>

For every recorded run it reports three scores against the same ground truth:
  * ``official``: copied verbatim from the official results file (``--official``), when given;
  * ``scorer_only``: the current scorer applied to the run as recorded, keeping the task-alignment
    verdict the agent computed at the time;
  * ``rescored``: task alignment recomputed from the recorded task spec, synthesis and evidence with
    the current alignment code, then scored by the current scorer.
Nothing is executed again: the evidence, SQL results and answers are exactly what the model produced.

It also scores deliberately wrong variants of recorded answers (``--counterfactuals``), to show that
the current criteria still reject wrong conclusions.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

from databeacon.agent.alignment import TaskSpec, check_alignment

from .metrics import aggregate, score_case
from .run import resolve_gold

CASES = Path(__file__).with_name("cases.json")


def realign(run: dict[str, Any]) -> dict[str, Any]:
    """The run with its task-alignment verdict recomputed by the current code."""
    run = copy.deepcopy(run)
    result = run.get("result") or {}
    if not result.get("spec") or not result.get("synthesis"):
        return run  # crashed before synthesis: nothing to re-check
    fields = TaskSpec.__dataclass_fields__
    spec = TaskSpec(**{k: v for k, v in result["spec"].items() if k in fields})
    result["alignment"] = check_alignment(spec, result["synthesis"], result.get("evidence", []))
    if run.get("status") in ("completed", "completed_with_issues"):
        aligned = result["alignment"]["status"] == "aligned"
        ver = result.get("verification") or {}
        run["status"] = "completed" if aligned and not ver.get("hallucination_rate") else "completed_with_issues"
    return run


def _sub(text: str, new: str, pattern: str = r"October\s+2025") -> str:
    out, n = re.subn(pattern, new, text)
    if not n:
        raise SystemExit(f"counterfactual could not edit the summary: no match for {pattern!r}")
    return out


def counterfactuals(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Wrong answers built from a recorded revenue_trend run (same evidence, wrong conclusion)."""
    out = {}
    wrong_month = copy.deepcopy(run)
    syn = wrong_month["result"]["synthesis"]
    syn["answer"]["primary_entity"] = "2025-03"
    syn["summary"] = _sub(syn["summary"], "March 2025")
    out["wrong_month_march_2025"] = wrong_month

    wrong_year = copy.deepcopy(run)
    syn = wrong_year["result"]["synthesis"]
    syn["answer"]["primary_entity"] = "2024-10"
    syn["summary"] = _sub(syn["summary"], "October 2024")
    out["wrong_year_october_2024"] = wrong_year

    unrelated = copy.deepcopy(run)
    syn = unrelated["result"]["synthesis"]
    syn["answer"]["dimension"] = "ship_month"
    for e in unrelated["result"]["evidence"]:
        if e["id"] in syn["answer"].get("evidence_ids", []):
            e["args"] = {**e["args"], "time_column": "ship_date"}
            e["sql"] = (e.get("sql") or "").replace("order_date", "ship_date")
    out["unrelated_date_column_ship_date"] = unrelated

    unstated = copy.deepcopy(run)
    syn = unstated["result"]["synthesis"]
    syn["summary"] = _sub(syn["summary"], "late in the year", r"in\s+October\s+2025")
    out["conclusion_not_in_summary"] = unstated
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs-db", required=True)
    ap.add_argument("--datasets-dir", required=True)
    ap.add_argument("--run", action="append", required=True, metavar="CASE=RUN_ID")
    ap.add_argument("--counterfactuals", metavar="CASE=RUN_ID", help="also score wrong variants of this run")
    ap.add_argument("--daily-variant", metavar="CASE=RUN_ID",
                    help="also score this run as if the question had asked for daily analysis")
    ap.add_argument("--official", help="official results JSON whose per-case scores are quoted unchanged")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    from databeacon.datasets import DatasetRegistry
    from databeacon.runs import RunStore

    store = RunStore(Path(args.runs_db))
    registry = DatasetRegistry(Path(args.datasets_dir))
    by_id = {c["id"]: c for c in json.loads(CASES.read_text())}

    def load(spec: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        case_id, run_id = spec.split("=", 1)
        case, run = by_id[case_id], store.get(run_id)
        if not run or run.get("question") != case["question"]:
            raise SystemExit(f"run {run_id} is not a recorded run of {case_id}")
        return case, run, resolve_gold(registry.db_path(run["dataset_id"]), case, by_id)

    official = {}
    if args.official:
        official = {c["case"]: c for c in json.loads(Path(args.official).read_text())["cases"]}
    keep = ("task_success", "checks", "alignment_issues")
    rows, original, rescored = [], [], []
    for spec in args.run:
        case, run, gold = load(spec)
        before, after = score_case(case, run, gold), score_case(case, realign(run), gold)
        for s in (before, after):
            s["expect_success"] = case.get("expect_success", True)
        original.append(before)
        rescored.append(after)
        row = {"case": case["id"], "run_id": run["id"]}
        if case["id"] in official:
            row["official"] = {k: official[case["id"]].get(k) for k in keep}
        row["scorer_only"] = {k: before[k] for k in keep}
        row["rescored"] = {k: after[k] for k in keep}
        rows.append(row)

    extra: dict[str, Any] = {}
    if args.counterfactuals:
        case, run, gold = load(args.counterfactuals)
        for name, variant in counterfactuals(run).items():
            s = score_case(case, realign(variant), gold)
            extra[name] = {k: s[k] for k in keep}
    if args.daily_variant:
        case, run, gold = load(args.daily_variant)
        daily_case = {**case, "question": case["question"].replace("monthly", "daily")}
        variant = copy.deepcopy(run)
        variant["question"] = daily_case["question"]
        variant["result"]["spec"]["question"] = daily_case["question"]
        s = score_case(daily_case, realign(variant), {**gold, "entity": "2025-10-01"})
        extra["daily_question_answered_with_monthly_buckets"] = {
            k: s[k] for k in ("task_success", "checks", "alignment_issues")}

    report = {"llm_calls": 0, "neurons": 0, "cases": rows,
              "summary": {"scorer_only": aggregate(original), "rescored": aggregate(rescored)},
              "counterfactuals": extra}
    Path(args.out).write_text(json.dumps(report, indent=2, default=str))
    def mark(r: dict[str, Any], k: str) -> str:
        return "-" if k not in r else ("pass" if r[k]["task_success"] else "fail")

    for r in rows:
        print(f"{r['case']:30} official={mark(r, 'official')} scorer_only={mark(r, 'scorer_only')} "
              f"rescored={mark(r, 'rescored')}")
    for name, s in extra.items():
        print(f"counterfactual {name:45} {'PASS (bad)' if s['task_success'] else 'rejected'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
