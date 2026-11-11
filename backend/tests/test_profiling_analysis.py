import pandas as pd

from databeacon import analysis as A
from databeacon.profiling import profile_table, schema_summary
from databeacon.sql_guard import query_df


def test_profile_roles_and_quality(registry, dataset):
    prof = profile_table(registry.db_path(dataset.id), dataset.table)
    roles = {c["name"]: c["role"] for c in prof["columns"]}
    assert roles["order_date"] == "temporal"
    assert roles["revenue"] == "numeric"
    assert roles["customer_segment"] == "categorical"
    assert roles["order_id"] == "identifier"
    assert roles["customer_id"] == "identifier"
    ship = next(c for c in prof["columns"] if c["name"] == "days_to_ship")
    assert 1.5 < ship["missing_pct"] < 5
    assert "ecommerce_orders" in schema_summary(prof)


def test_contribution_finds_planted_segment(registry, dataset):
    sql = ("SELECT customer_segment, region, CASE WHEN order_date >= '2025-10-01' THEN 'current' ELSE 'previous' END "
           "AS period, SUM(revenue) AS value FROM ecommerce_orders WHERE order_date >= '2025-07-01' GROUP BY ALL")
    res = A.contribution(query_df(registry.db_path(dataset.id), sql), ["customer_segment", "region"])
    worst = res["top_negative_contributors"][0]
    assert (worst["customer_segment"], worst["region"]) == ("SMB", "West")
    assert res["total_pct_change"] < -10


def test_compare_groups_and_trend(registry, dataset):
    df = query_df(registry.db_path(dataset.id),
                  "SELECT product_category, discount_pct FROM ecommerce_orders WHERE order_date >= '2025-10-01'")
    res = A.compare_groups(df, "product_category", "discount_pct")
    assert res["significant"] and res["groups"][0]["group"] == "Electronics"
    df = query_df(registry.db_path(dataset.id), "SELECT order_date, revenue FROM ecommerce_orders")
    tr = A.trend(df, "order_date", "revenue", freq="month")
    assert tr["points"] == 24 and tr["change_point"]["period"].startswith("2025-10")


def test_anomalies_and_correlation():
    df = pd.DataFrame({"v": [10, 11, 9, 10, 12, 10, 95, 11, 10, 9], "w": range(10)})
    an = A.detect_anomalies(df, "v", "iqr")
    assert an["anomaly_count"] == 1 and an["anomalies"][0]["value"] == 95
    corr = A.correlation(df.assign(z=lambda d: d.w * 2 + 1))
    assert corr["pairs"][0]["coefficient"] == 1.0


def test_preview_handles_every_tool_output_shape():
    """Regression: descriptive_statistics returns {"rows": n, "columns": {name: stats}}; the
    preview indexed it like a list and the KeyError aborted a live investigation."""
    import pandas as pd

    from databeacon.agent.evidence import preview_table, summarize
    from databeacon.analysis import describe

    stats = describe(pd.DataFrame({"revenue": [1.0, 2.0, None], "units": [1, 2, 3], "seg": list("abc")}))
    p = preview_table(stats)
    assert p["columns"][0] == "column" and "mean" in p["columns"]
    assert [r[0] for r in p["rows"]] == ["revenue", "units"]
    for odd in ({"columns": {}, "rows": 3}, {"columns": [], "rows": []}, {"segments": ["x"]},
                {"data": {"rows": 1}}, {"columns": {"a": 1}, "rows": 2}, [], None, "text"):
        preview_table(odd)  # never raises
    assert summarize("descriptive_statistics", stats)


def test_pdf_text_has_no_undrawable_characters(tmp_path):
    """Regression: a non-breaking hyphen ("one‑off") printed as a black box in the PDF."""
    import pypdf

    from databeacon.reporting.pdf import build_pdf, pdf_text

    assert pdf_text("one‑off ≤ 5 → ok, café, 12°C, 20 %") == "one-off <= 5 -> ok, café, 12°C, 20 %"
    out = tmp_path / "r.pdf"
    build_pdf(out, {"title": "Seasonal one‑off", "question": "q", "dataset": "d", "summary": "A one‑off promo.",
                    "findings": [], "charts": [], "evidence": [], "limitations": ["Seasonal or one‑off effects."],
                    "timeline": [], "metrics": {}, "scope": {}})
    text = "".join(p.extract_text() for p in pypdf.PdfReader(out).pages)
    assert "one-off" in text and "■" not in text
