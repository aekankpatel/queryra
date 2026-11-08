"""Bundled sample datasets: catalog, licences on file, loading through the API, and their contents."""

import csv
import json
from pathlib import Path

import pytest
from test_replays import _client, _no_llm

SAMPLE_DIR = Path(__file__).resolve().parents[1] / "sample_data"
CATALOG = json.loads((SAMPLE_DIR / "catalog.json").read_text())
BUNDLED = [s for s in CATALOG if s["id"] != "ecommerce"]
EXPECTED = {  # rows, columns and types after ingestion
    "seattle-weather": (1461, {"date": "DATE", "precipitation": "DOUBLE", "weather": "VARCHAR"}),
    "us-employment": (120, {"date": "DATE", "nonfarm": "BIGINT", "manufacturing": "BIGINT"}),
    "iowa-electricity": (51, {"date": "DATE", "energy_source": "VARCHAR", "net_generation": "BIGINT"}),
    "palmer-penguins": (344, {"species": "VARCHAR", "study_year": "BIGINT", "body_mass_g": "BIGINT", "bill_length_mm": "DOUBLE"}),
}


def test_catalog_entries_are_complete_and_documented():
    sources = (SAMPLE_DIR / "SOURCES.md").read_text()
    assert {s["id"] for s in BUNDLED} == set(EXPECTED)
    for s in CATALOG:
        assert s["name"] and s["license"] and s["source"] and len(s["examples"]) >= 3
        assert s["file"] in sources  # every file has a source and licence on record
    for s in BUNDLED:
        path = SAMPLE_DIR / s["file"]
        assert path.is_file() and path.stat().st_size < 1_000_000  # small enough for the function bundle
        with path.open(newline="") as fh:
            rows = list(csv.reader(fh))
        assert len(rows) - 1 == EXPECTED[s["id"]][0]
        assert "NA" not in {v for r in rows[1:] for v in r}  # missing values are empty fields


@pytest.mark.parametrize("sample", sorted(EXPECTED))
def test_each_sample_loads_with_correct_types(registry, monkeypatch, sample):
    h = {"X-DataBeacon-Session": f"{sample[:4]}".ljust(32, "s")}
    with _client(registry, _no_llm, monkeypatch) as c:
        r = c.post(f"/api/datasets/sample?sample={sample}", headers=h)
        assert r.status_code == 201, r.text
        ds = r.json()
        rows, types = EXPECTED[sample]
        assert ds["row_count"] == rows and ds["name"] == next(s["name"] for s in CATALOG if s["id"] == sample)
        got = {col["name"]: col["type"] for col in ds["columns"]}
        assert {k: got.get(k) for k in types} == types
        assert not [n for n in got if n.startswith("_")]  # no reserved-word renames by the CSV reader
        assert c.post(f"/api/datasets/sample?sample={sample}", headers=h).json()["id"] == ds["id"]  # one copy
        prof = c.get(f"/api/datasets/{ds['id']}/profile", headers=h)
        assert prof.status_code == 200
        q = c.post(f"/api/datasets/{ds['id']}/sql", headers=h, json={"sql": f'SELECT COUNT(*) FROM "{ds["table"]}"'})
        assert q.json()["rows"][0][0] == rows


def test_sample_list_and_unknown_sample(registry, monkeypatch):
    h = {"X-DataBeacon-Session": "l" * 32}
    with _client(registry, _no_llm, monkeypatch) as c:
        listed = c.get("/api/samples").json()
        assert [s["id"] for s in listed][0] == "ecommerce" and len(listed) == len(CATALOG)
        assert c.post("/api/datasets/sample?sample=../../etc/passwd", headers=h).status_code == 404
        assert c.post("/api/datasets/sample?sample=nope", headers=h).status_code == 404
        assert c.post("/api/datasets/sample", headers=h).json()["name"] == "E-commerce orders (sample)"  # default


def test_penguin_missing_values_are_real_nulls(registry, monkeypatch):
    h = {"X-DataBeacon-Session": "p" * 32}
    with _client(registry, _no_llm, monkeypatch) as c:
        ds = c.post("/api/datasets/sample?sample=palmer-penguins", headers=h).json()
        prof = c.get(f"/api/datasets/{ds['id']}/profile", headers=h).json()
        missing = {col["name"]: col["missing"] for col in prof["columns"]}
        assert missing["sex"] == 11 and missing["body_mass_g"] == 2
