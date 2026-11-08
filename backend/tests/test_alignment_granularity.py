"""Regression tests for granularity-aware task alignment: derived time groupings, dates compared at the
requested granularity, and written-out dates. Every relaxation has a negative test next to it."""

import pytest

from databeacon.agent.alignment import (
    TaskSpec,
    _entity_match,
    check_alignment,
    date_refs,
    derived_time_groupings,
    entity_stated,
    requested_grain,
)
from evals.metrics import score_case

MONTHLY_Q = "Is monthly revenue trending up or down, and when did the most significant shift happen?"
DAILY_Q = "Show daily revenue: on which day did revenue drop the most?"


def _spec(question=MONTHLY_Q, group_by=("order_date",)):
    return TaskSpec(question=question, question_type="trend", metric_column="revenue", aggregation="sum",
                    group_by=list(group_by), answer_target="when the shift happened")


def _sql_ev(eid, unit, col, alias):
    sql = (f"SELECT DATE_TRUNC('{unit}', \"{col}\") AS {alias}, SUM(\"revenue\") AS rev "
           f"FROM \"ecommerce_orders\" GROUP BY {alias} ORDER BY {alias}")
    return {"id": eid, "tool": "run_sql", "ok": True, "args": {"sql": sql}, "sql": sql,
            "data": {"columns": [alias, "rev"], "rows": []}, "preview": None}


def _trend_ev(eid, col="order_date", freq="month"):
    return {"id": eid, "tool": "trend_analysis", "ok": True, "sql": f'SELECT "{col}", "revenue" FROM t',
            "args": {"sql": f'SELECT "{col}", "revenue" FROM t', "time_column": col, "value_column": "revenue",
                     "freq": freq, "agg": "sum"},
            "data": {"change_point": {"period": "2025-10-01", "mean_shift": -60712.17}}, "preview": None}


def _syn(entity, dim, summary, eid="E2"):
    return {"summary": summary, "findings": [{"title": "t", "statement": "s", "evidence_ids": [eid]}],
            "answer": {"primary_entity": entity, "dimension": dim, "metric_column": "revenue",
                       "direction": "change_point", "evidence_ids": [eid]}}


GOOD_SUMMARY = ("Monthly revenue shows a slight, not significant decline (p = 0.48). A pronounced shift occurs "
                "in October 2025, when mean monthly revenue drops by about $60,712 (E2).")


# ---------------------------------------------------------------- requested granularity
@pytest.mark.parametrize("q,grain", [
    (MONTHLY_Q, "month"), (DAILY_Q, "day"), ("Weekly orders by region", "week"),
    ("Which quarter had the highest revenue?", "quarter"), ("Year-over-year revenue growth", "year"),
    ("Why did revenue decline last quarter?", None),  # a period, not a grouping granularity
    ("Average days_to_ship by region", None),  # column names are not granularity words
    ("Monthly revenue, and which day was worst?", None),  # conflicting -> unspecified
])
def test_requested_grain(q, grain):
    assert requested_grain(q) == grain


# ---------------------------------------------------------------- 1. derived time groupings
def test_derived_groupings_from_sql_and_tools():
    d = derived_time_groupings([_sql_ev("E1", "month", "order_date", "month"), _trend_ev("E2", freq="W"),
                                {"id": "E3", "tool": "run_sql", "ok": True, "args": {}, "sql":
                                 "SELECT strftime(ship_date, '%Y-%m') AS ship_month, CAST(order_date AS DATE) AS d "
                                 "FROM t"}])
    assert d["month"] == ("month", "order_date")
    assert d["week"] == ("week", "order_date")
    assert d["ship_month"] == ("month", "ship_date")
    assert d["d"] == ("day", "order_date")


def test_month_of_requested_date_column_is_accepted():
    a = check_alignment(_spec(), _syn("2025-10", "month", GOOD_SUMMARY), [_trend_ev("E2")])
    assert a["checks"]["grouping"] == "pass", a["issues"]
    a = check_alignment(_spec(), _syn("2025-10", "month", GOOD_SUMMARY, eid="E1"),
                        [_sql_ev("E1", "month", "order_date", "month")])
    assert a["checks"]["grouping"] == "pass", a["issues"]


def test_unrelated_date_column_is_not_equivalent():
    a = check_alignment(_spec(), _syn("2025-10", "ship_month", GOOD_SUMMARY, eid="E1"),
                        [_sql_ev("E1", "month", "ship_date", "ship_month")])
    assert a["checks"]["grouping"] == "fail"
    assert any("month of ship_date" in i for i in a["issues"])


def test_unknown_dimension_still_fails():
    a = check_alignment(_spec(), _syn("2025-10", "region", GOOD_SUMMARY), [_trend_ev("E2")])
    assert a["checks"]["grouping"] == "fail"


def test_monthly_aggregation_does_not_satisfy_daily_request():
    # derived alias at the wrong grain
    a = check_alignment(_spec(DAILY_Q), _syn("2025-10-14", "month", "Revenue fell most on 2025-10-14.", eid="E1"),
                        [_sql_ev("E1", "month", "order_date", "month")])
    assert a["checks"]["grouping"] == "fail"
    assert any("daily analysis" in i for i in a["issues"])
    # even when the answer names the raw date column, monthly buckets do not answer a daily question
    a = check_alignment(_spec(DAILY_Q), _syn("2025-10-14", "order_date", "Revenue fell most on 2025-10-14.", eid="E1"),
                        [_sql_ev("E1", "month", "order_date", "order_month")])
    assert a["checks"]["grouping"] == "fail"
    # daily buckets do
    a = check_alignment(_spec(DAILY_Q), _syn("2025-10-14", "day", "Revenue fell most on 2025-10-14.", eid="E1"),
                        [_sql_ev("E1", "day", "order_date", "day")])
    assert a["checks"]["grouping"] == "pass", a["issues"]


def test_daily_aggregation_does_not_satisfy_monthly_request():
    a = check_alignment(_spec(), _syn("2025-10", "day", GOOD_SUMMARY, eid="E1"),
                        [_sql_ev("E1", "day", "order_date", "day")])
    assert a["checks"]["grouping"] == "fail"


# ---------------------------------------------------------------- 2. granularity-aware date comparison
@pytest.mark.parametrize("a,b", [("2025-10", "2025-10-01"), ("2025-10-01", "October 2025"), ("Oct 2025", "2025-10"),
                                 ("2025/10", "2025-10-31")])
def test_equivalent_months_match_at_month_grain(a, b):
    assert _entity_match(a, b, "month")


@pytest.mark.parametrize("a,b", [("2025-09", "2025-10-01"), ("September 2025", "2025-10"), ("2024-10", "2025-10"),
                                 ("2025-10", "2025-11-01")])
def test_different_months_do_not_match(a, b):
    assert not _entity_match(a, b, "month")


def test_day_grain_needs_the_same_day():
    assert _entity_match("2025-10-14", "October 14, 2025", "day")
    assert not _entity_match("2025-10-14", "2025-10-15", "day")
    assert not _entity_match("2025-10", "2025-10-01", "day")  # a month is not a day
    assert not _entity_match("October 2025", "2025-10-14", "day")


def test_quarter_and_year_grains():
    assert _entity_match("2025-11", "2025-10-01", "quarter")
    assert not _entity_match("2025-09", "2025-10-01", "quarter")
    assert _entity_match("March 2025", "2025-12-31", "year") and not _entity_match("2024-12", "2025-01", "year")


# ---------------------------------------------------------------- 3. written-out dates
@pytest.mark.parametrize("text,ref", [
    ("in October 2025", (2025, 10, None)), ("Oct. 2025", (2025, 10, None)), ("Sept 2025", (2025, 9, None)),
    ("October 1, 2025", (2025, 10, 1)), ("Oct 1st 2025", (2025, 10, 1)), ("1 October 2025", (2025, 10, 1)),
    ("the 3rd of March, 2024", (2024, 3, 3)), ("2025-10", (2025, 10, None)), ("2025-10-01", (2025, 10, 1)),
])
def test_written_dates_are_read(text, ref):
    assert date_refs(text) == [ref]


@pytest.mark.parametrize("text", ["2025-13", "2025-13-01", "June 31, 2025", "we may 2025", "order 12345-10",
                                  "may grow", "October"])
def test_invalid_or_partial_dates_are_ignored(text):
    assert date_refs(text) == []


def test_summary_must_state_the_conclusion_month():
    assert entity_stated("2025-10", GOOD_SUMMARY, "month")
    assert not entity_stated("2025-10", GOOD_SUMMARY.replace("October 2025", "September 2025"), "month")
    assert not entity_stated("2025-10", "Revenue shifted in late 2025.", "month")
    a = check_alignment(_spec(), _syn("2025-10", "month", GOOD_SUMMARY.replace("October 2025", "the autumn")),
                        [_trend_ev("E2")])
    assert a["checks"]["primary_conclusion"] == "fail"


# ---------------------------------------------------------------- scorer: correct passes, wrong conclusions fail
CASE = {"id": "revenue_trend", "question": MONTHLY_Q, "expected_tools": ["trend_analysis"], "acceptable_tools": []}
GOLD = {"entity": "2025-10-01", "metric_column": "revenue", "numbers": []}


def _run(entity, summary, dim="month", ev=None):
    ev = ev or [_trend_ev("E2")]
    syn = _syn(entity, dim, summary)
    al = check_alignment(_spec(), syn, ev)
    return {"status": "completed" if al["status"] == "aligned" else "completed_with_issues",
            "result": {"evidence": ev, "synthesis": syn, "alignment": al,
                       "verification": {"hallucination_rate": 0.0}, "metrics": {}}}


def test_scorer_accepts_equivalent_month_and_rejects_wrong_ones():
    assert score_case(CASE, _run("2025-10", GOOD_SUMMARY), GOLD)["task_success"]
    assert score_case(CASE, _run("October 2025", GOOD_SUMMARY), GOLD)["task_success"]
    wrong = GOOD_SUMMARY.replace("October 2025", "March 2025")
    s = score_case(CASE, _run("2025-03", wrong), GOLD)
    assert not s["task_success"] and s["checks"]["primary_conclusion"] == "fail"
    s = score_case(CASE, _run("2024-10", GOOD_SUMMARY.replace("October 2025", "October 2024")), GOLD)
    assert not s["task_success"]  # right month name, wrong year
    s = score_case(CASE, _run("2025-10", GOOD_SUMMARY, dim="ship_month",
                              ev=[_sql_ev("E2", "month", "ship_date", "ship_month")]), GOLD)
    assert not s["task_success"] and s["checks"]["alignment"] == "fail"


def test_daily_gold_is_not_satisfied_by_a_month():
    case = {**CASE, "question": DAILY_Q}
    gold = {**GOLD, "entity": "2025-10-14"}
    assert not score_case(case, _run("2025-10", "Revenue dropped most in October 2025."), gold)["checks"][
        "primary_conclusion"] == "pass"
