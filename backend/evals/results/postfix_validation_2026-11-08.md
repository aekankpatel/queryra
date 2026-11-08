# Post-fix validation — 2026-11-08

**This is not part of the official benchmark.** The official six-case result stays **4/6**
(`benchmark_cloudflare_gpt-oss-120b_2026-11-07_resumed.{json,md}`, unchanged). This report records
tests run afterwards.

## 1. `data_quality` rerun after the bug fix (explicitly approved)

Same model (`@cf/openai/gpt-oss-120b` on Cloudflare Workers AI), agent configuration
(`MAX_ITERATIONS=2`, `MAX_STEPS_PER_ITERATION=6`), ground truth and scoring criteria. No fallback, no
paid inference. The rerun fixes this bug: `preview_table` crashed with `KeyError: 0` on
`descriptive_statistics` output. This run called `descriptive_statistics` again and handled it.

| | |
|---|---|
| Run | `c4ca4762f66d`, 2026-11-08T07:06Z |
| Result | **pass**: every check passed |
| Correctness (primary conclusion `days_to_ship`) | pass |
| Task alignment | pass (no issues) |
| SQL validity | 1.0 |
| Evidence verification | 5/5 findings verified, hallucination rate 0.0, gold numbers in cited evidence |
| Tool selection | precision 1.0, recall 1.0, F1 1.0 (`run_sql`, `detect_anomalies` ×3, `descriptive_statistics`, `run_sql`) |
| Tool errors | 0 |
| Latency | 38.98 s |
| LLM calls / tool calls | 9 / 7 (6 chosen by the agent) |
| Tokens | 27444 (plan 1,798 · act 19,051 · reflect 2,865 · synthesize 3,730) |
| Neurons | 1016.6 + 5.5 preflight |

Budget: before the run the guard showed 5,170 neurons used in its rolling 24 h window and 3,830
remaining (guard limit 9,000; free allocation 10,000). Cap for this validation: 3,500. A first attempt
with a 2,000 cap stopped before the case, because the harness reserves a 3,000-neuron worst case per
case. Only its preflight call (5.5 neurons) ran. No quota errors.

## 2. `revenue_trend`: why the official run failed

Question: *"Is monthly revenue trending up or down, and when did the most significant shift happen?"*
Gold: change point in month **2025-10-01** (start of the planted Q4-2025 drop), metric `revenue`.

**What the agent did** (run `b956ca14649a`):
- E1 `run_sql`: `SUM(revenue)` grouped by `DATE_TRUNC('month', order_date)`, 24 months.
- E2 `trend_analysis(order_date, revenue, freq=month, agg=sum)`: slope −1,037/month, R² 0.023,
  p = 0.48 (Mann–Kendall p = 0.34), so decreasing but not significant. Change point
  **2025-10-01**, mean shift **−60,712**.
- E3 `run_sql`: the largest single month-over-month jump is March 2025 (+28.5%).
- E4 a line chart of monthly revenue.
- Answer: `primary_entity = "2025-10"`, `dimension = "month"`, citing E2. Summary: *"…slight
  decreasing trend… not statistically significant (p = 0.48). A pronounced shift occurs in October
  2025, where the mean monthly revenue drops by approximately $60,712…"*. Verification: 3/3
  findings and 9/9 numeric claims supported.

**Assertions that failed** (all unchanged):

| Check | Assertion | Values | Result |
|---|---|---|---|
| Agent alignment: grouping | `answer.dimension ∈ spec.group_by` | `"month"` vs `["order_date"]` | fail |
| Agent alignment: conclusion | entity text appears in summary | `"2025-10"` vs "October 2025" | fail |
| Scorer: primary conclusion | `_entity_match("2025-10", "2025-10-01")` | date regex needs `YYYY-MM-DD` | fail |
| Scorer: primary conclusion | gold entity stated in summary | "October 2025", no ISO date | fail |
| Scorer: alignment | run alignment = aligned | misaligned (from the two agent-side failures) | fail |

**Verdict: the evaluator is too restrictive. The analysis is not wrong.** The agent did the right
thing at each step:
- It aggregated `order_date` by month, which is what "monthly" asks for.
- It found the gold month.
- It answered both parts of the question.
- It backed every number with evidence.
- It correctly chose the sustained mean shift (E2) over the single largest month-to-month jump (E3).

All three failures are literal comparisons:
- a time grain derived from the requested date column;
- `YYYY-MM` vs `YYYY-MM-DD` for the same month;
- a written-out month name.

**Proposed (not applied; needs your approval):**
- Treat `month`/`quarter`/`week` of the requested date column as matching it.
- Compare `YYYY-MM` with `YYYY-MM-DD` at month resolution.
- Accept written month names when checking that the summary states a month.

The same alignment check runs in the product, so today a user would see this correct answer marked
*completed with issues*. After a change, the official run would have to be re-scored or rerun,
and that would be reported as a new result, separate from the official 4/6.

## Summary

| | Official benchmark (2026-11-07/08) | After the fix (this report) |
|---|---|---|
| Score | **4/6** (official, unchanged) | `data_quality` rerun: pass |
| data_quality | crashed (code bug) | pass, 1,016.6 neurons, 39 s |
| revenue_trend | failed the strict scorer | not rerun; analysis judged correct, evaluator too literal |
