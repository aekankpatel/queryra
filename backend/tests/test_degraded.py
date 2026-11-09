"""The API stays up when shared storage cannot be reached, and says why without leaking secrets."""

from fastapi.testclient import TestClient

from databeacon.diagnostics import redact

H = {"X-DataBeacon-Session": "q" * 32}


def test_unreachable_d1_starts_degraded_not_crashed(monkeypatch, tmp_path):
    from databeacon.config import reset_settings_cache
    from databeacon.storage import factory

    secret = "tok_" + "x" * 36
    monkeypatch.setenv("DATABEACON_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABEACON_STORAGE", "d1")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "0123456789abcdef0123456789abcdef")
    monkeypatch.setenv("DATABEACON_D1_DATABASE_ID", "11111111-2222-3333-4444-555555555555")
    monkeypatch.setenv("DATABEACON_D1_API_TOKEN", secret)
    monkeypatch.setenv("DATABEACON_D1_BASE_URL", "http://127.0.0.1:9")  # nothing listens here
    monkeypatch.setenv("DATABEACON_PUBLIC_MODE", "1")
    reset_settings_cache()
    factory.reset_stores()
    try:
        from databeacon.api.main import create_app

        with TestClient(create_app()) as c:
            h = c.get("/api/health").json()
            assert h["status"] == "degraded" and "StorageError" in h["storage_error"]
            body = str(h)
            assert secret not in body and "0123456789abcdef0123456789abcdef" not in body
            assert "11111111-2222-3333-4444-555555555555" not in body
            assert c.get("/api/replays").status_code == 200
            assert c.get("/api/replays/return-rate/report.pdf").content[:4] == b"%PDF"
            assert c.get("/api/samples").status_code == 200
            r = c.get("/api/datasets", headers=H)
            assert r.status_code == 503 and "Recorded investigations still work" in r.json()["detail"]
            assert c.post("/api/datasets/sample", headers=H).status_code == 503
            assert c.get("/api/usage").status_code == 503
    finally:
        reset_settings_cache()
        factory.reset_stores()


def test_redact_removes_ids_tokens_and_paths(monkeypatch):
    monkeypatch.setenv("SOME_API_TOKEN", "short-but-secret")
    text = ("token short-but-secret, account 0123456789abcdef0123456789abcdef, db "
            "11111111-2222-3333-4444-555555555555, key abcdefghijklmnopqrstuvwxyz0123456789, "
            "file /var/task/backend/x.py: Authentication error (HTTP 403)")
    out = redact(text)
    for bad in ("short-but-secret", "0123456789abcdef", "11111111-2222", "abcdefghijklmnop", "/var/task"):
        assert bad not in out
    assert "Authentication error (HTTP 403)" in out
