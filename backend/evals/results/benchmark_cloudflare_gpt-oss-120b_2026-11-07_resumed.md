# DataBeacon six-case benchmark — resumed after an interruption

Cloudflare Workers AI `@cf/openai/gpt-oss-120b`, no fallback, no paid inference, same agent budgets
(`MAX_ITERATIONS=2`, `MAX_STEPS_PER_ITERATION=6`) and the same strict criteria as the first attempt.
Run 2026-11-08T00:53Z.

**Provenance.** The first attempt (2026-11-07) stopped before finishing. Four completed runs were
reused unchanged; `revenue_trend` and `data_quality` ran fresh. Earlier records are kept, not
overwritten: `52bb4af8bb12` (interrupted), `8a77b15dcd32` (failed on the Cloudflare daily quota,
error 4006, not reused) and `c8b43832909f` (killed). See also
`benchmark_cloudflare_gpt-oss-120b_2026-11-07_incomplete.{json,md}`.

| Case | Run | Source | Latency | LLM calls | Tool calls | Neurons |
|---|---|---|---|---|---|---|
| revenue_decline_attribution | `0848f476efd2` | reused | 84.35 s | 7 | 5 | 822.7 |
| discount_shift | `daed68f13aa5` | reused | 72.69 s | 7 | 4 | 720.6 |
| shipping_by_region | `24962e3ca49f` | reused | 57.19 s | 9 | 4 | 742.3 |
| return_rate | `0825f25a9997` | reused | 63.64 s | 9 | 3 | 645.3 |
| revenue_trend | `b956ca14649a` | fresh | 80.28 s | 11 | 5 | 1340.2 |
| data_quality | `2d4a5933169e` | fresh | 12.86 s | 3 | 3 | 276.5 |

Neurons this session: 1616.7 (incl. preflight 5.9), on top of 3547.3 from the first attempt; benchmark cap 7,000; Cloudflare free allocation 10,000/day. Total across both attempts, including interrupted work: 5169.9.

## Notes on the two failures (criteria unchanged)

- **revenue_trend: failed the strict scorer, but the answer is correct in substance.** The agent found the
  change point in October 2025 (mean monthly revenue −$60,712, evidence E2), with an insignificant
  overall slope (p = 0.48). The task-alignment check rejected it for grouping by `month` when the
  question names `order_date` (month is derived from `order_date`), and because the summary writes
  "October 2025" rather than `2025-10`. This looks like the alignment checker being too literal for
  derived time grains and written-out month names. Not changed here; proposed as a follow-up.
- **data_quality: crashed on a code bug, not on the model or the budget.** The agent called
  `descriptive_statistics`, whose output has `columns` as a mapping of per-column statistics, and
  the timeline preview indexed it like a list (`KeyError: 0`). Fixed after this run: the preview now
  renders per-column statistics, and formatting errors can no longer abort an investigation
  (regression test `test_preview_handles_every_tool_output_shape`). Not rerun, per the
  no-automatic-rerun rule.



Mode: `live` · Provider: `cloudflare` · Model: `@cf/openai/gpt-oss-120b` · Budgets: `{'max_iterations': 2, 'max_tool_calls': 24, 'max_steps_per_iteration': 6}`

A case succeeds only if every check passes: primary conclusion (structured answer), period, metric, grouping, gold numbers in cited evidence, task alignment and hallucination <= 10%.

## Aggregate

| Metric | Value |
|---|---|
| cases | 6 |
| task success rate | 0.667 |
| primary conclusion rate | 0.667 |
| period correct rate | 1.0 |
| metric correct rate | 1.0 |
| grouping correct rate | 1.0 |
| numerical evidence rate | 0.833 |
| alignment rate | 0.667 |
| sql validity | 1.0 |
| tool selection f1 | 0.8 |
| hallucination rate | 0.0 |
| avg latency s | 61.835 |
| avg total tokens | 19164.333 |
| avg tool calls | 4.0 |
| error recovery rate | 0.0 |
| scorer calibration | 0.667 |
| total cloudflare neurons | 4547.6 |
| benchmark neurons incl interrupted work | 5169.9 |

## Per case

| Case | Expected | Success | Conclusion | Period | Metric | Grouping | Numbers | Aligned | Halluc. | Tokens |
|---|---|---|---|---|---|---|---|---|---|---|
| revenue_decline_attribution | pass | ✅ | pass | pass | pass | pass | pass | pass | 0.0 | 20246 |
| discount_shift | pass | ✅ | pass | pass | pass | pass | pass | pass | 0.0 | 18251 |
| shipping_by_region | pass | ✅ | pass | n/a | pass | pass | pass | pass | 0.0 | 19616 |
| return_rate | pass | ✅ | pass | n/a | pass | pass | pass | pass | 0.0 | 16651 |
| revenue_trend | pass | ❌ | fail | n/a | pass | n/a | pass | fail | 0.0 | 33196 |
| data_quality | pass | ❌ | fail | n/a | n/a | n/a | fail | fail | None | 7026 |
