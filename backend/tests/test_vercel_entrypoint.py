"""api/index.py must expose a top-level ``app`` (Vercel's builder only detects module-level names),
and must still answer with a readable error if the real app cannot be imported."""

import ast
import importlib.util
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ENTRY = Path(__file__).resolve().parents[2] / "api" / "index.py"


def test_app_is_assigned_at_module_level():
    tree = ast.parse(ENTRY.read_text())
    top = [t.id for n in tree.body if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)]
    top += [a.asname or a.name for n in tree.body if isinstance(n, ast.ImportFrom) for a in n.names]
    assert "app" in top


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ENTRY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_entrypoint_serves_the_real_app():
    assert _load("vercel_entry_ok").app.title == "Queryra API"


def test_import_failure_is_reported_not_crashed(monkeypatch):
    monkeypatch.setitem(sys.modules, "databeacon.api.main", None)  # makes the import raise ImportError
    with TestClient(_load("vercel_entry_broken").app) as c:
        r = c.get("/api/health")
    assert r.status_code == 503 and r.json()["startup_error"].startswith(("ImportError", "ModuleNotFoundError"))
