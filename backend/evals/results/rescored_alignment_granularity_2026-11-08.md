# Retrospective rescoring: task-alignment granularity fix (2026-11-08)

**Retrospective rescoring of recorded runs. No new model executions:** 0 LLM calls, 0 neurons.
The evidence, SQL results and answers are exactly what the model produced on 2026-11-07/08.
**The official benchmark result stays 4/6**
(`benchmark_cloudflare_gpt-oss-120b_2026-11-07_resumed.{json,md}`, unchanged). The post-fix validation
(`postfix_validation_2026-11-08.{json,md}`) is also unchanged.

Reproduce: `python -m evals.rescore --runs-db … --datasets-dir … --official benchmark_…_resumed.json --run CASE=RUN_ID … --counterfactuals revenue_trend=b956ca14649a --daily-variant revenue_trend=b956ca14649a --out …`

## Result

| Case | Recorded run | Official (verbatim) | Current scorer, recorded alignment | Rescored (current alignment + scorer) |
|---|---|---|---|---|
| revenue_decline_attribution | `0848f476efd2` | ✅ pass | ✅ pass | ✅ pass |
| discount_shift | `daed68f13aa5` | ✅ pass | ✅ pass | ✅ pass |
| shipping_by_region | `24962e3ca49f` | ✅ pass | ✅ pass | ✅ pass |
| return_rate | `0825f25a9997` | ✅ pass | ✅ pass | ✅ pass |
| revenue_trend | `b956ca14649a` | ❌ fail | ❌ fail | ✅ pass |
| data_quality | `2d4a5933169e` | ❌ fail | ❌ fail | ❌ fail |
| **Task success** | | **4/6 (0.667)** | 0.667 | **5/6 (0.833)** |

- **revenue_trend** fail → pass. The scorer change alone fixes its primary-conclusion check
  (`2025-10` = gold `2025-10-01` at month level; "October 2025" is in the summary). The recomputed
  alignment fixes the rest: grouping by `month` (= `DATE_TRUNC('month', order_date)`) matches the
  requested `order_date` for a *monthly* question, and the summary states the conclusion month.
- **data_quality** stays a fail: the recorded run crashed (`KeyError: 0`, fixed since). Its
  approved post-fix rerun `c4ca4762f66d` is a separate execution, not part of this rescoring; under
  the new criteria it still passes.
- The four previously passing cases are unchanged.

## Criteria changed

| # | Before | After |
|---|---|---|
| 1. Derived time groupings (`alignment.check_alignment`, grouping) | the answer's dimension had to be literally one of the requested columns | Also accepted: a time bucket of a **requested** date column (a `DATE_TRUNC`/`strftime`/`CAST … AS DATE` alias, or `time_column`+`freq` of a time-series tool) at the **requested granularity**. Still rejected: buckets of another date column, or of another granularity. New: evidence that buckets the requested date column at the wrong granularity now fails, even when the answer names the raw column |
| 2. Granularity-aware dates (`_entity_match`, `entity_stated`, scorer primary conclusion) | dates matched only as full `YYYY-MM-DD`; `2025-10` never matched `2025-10-01` | compared at the granularity the question asks for (day/week/month/quarter/year; month if unspecified). A month without a day never satisfies a daily request |
| 3. Written dates (`date_refs`) | only ISO `YYYY-MM-DD` | also `YYYY-MM`, `YYYY/MM(/DD)`, "October 2025", "Oct. 2025", "October 1, 2025", "1 October 2025". Impossible dates (2025-13, 31 June) and lower-case "may" are ignored |

Requested granularity comes from explicit wording ("monthly", "per day", "which quarter", "year over
year"…). With conflicting wording it counts as unspecified. A period such as "last quarter", or a
column name such as `days_to_ship`, is not a granularity.

**Justification.** Run `b956ca14649a` answered correctly: change point 2025-10-01, −60,712, and 9/9
numeric claims verified. It failed only on literal comparisons (see `postfix_validation_2026-11-08.md`).
Each relaxation has negative tests, and wrong answers are still rejected:

## Wrong answers are still rejected (counterfactuals from the same recorded run)

| Variant | Outcome | Failed checks | Alignment issues |
|---|---|---|---|
| wrong month march 2025 | rejected | primary_conclusion | — |
| wrong year october 2024 | rejected | primary_conclusion | — |
| unrelated date column ship date | rejected | alignment | answer is grouped by 'ship_month' but the question asks for order_date |
| conclusion not in summary | rejected | alignment, primary_conclusion | the summary does not state the primary conclusion '2025-10' |
| daily question answered with monthly buckets | rejected | alignment, primary_conclusion | answer is grouped by month of order_date but the question asks for daily analysis; the summary does not state the primary conclusion '2025-10' |

43 new unit tests (`tests/test_alignment_granularity.py`) cover positive and negative cases for all
three changes, including a monthly answer to a daily question, daily buckets for a monthly
question, an unrelated date column, wrong month, wrong year, invalid dates and the verb "may".

**Known limitation (unchanged).** The agent's own alignment check cannot recompute a change-point
month from `trend_analysis` output. A self-consistent wrong month is therefore caught by the scorer's
comparison with the ground truth, not by the in-product check.
