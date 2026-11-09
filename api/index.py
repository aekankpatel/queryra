"""Vercel entrypoint: the Queryra FastAPI app as a Python function.

Vercel routes /api/* here (see vercel.json). The backend package lives in backend/.
If the app cannot even be imported (e.g. a dependency failed to install), a minimal app answers
instead, so /api/health says why rather than every request failing with FUNCTION_INVOCATION_FAILED.
Vercel only detects a *top-level* ``app``, so it is assigned at module level below.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))


def _fallback_app(reason: str):
    async def fallback(scope, receive, send):  # minimal ASGI app: needs no dependencies
        if scope["type"] == "lifespan":
            while (await receive())["type"] != "lifespan.shutdown":
                await send({"type": "lifespan.startup.complete"})
            await send({"type": "lifespan.shutdown.complete"})
            return
        import json

        body = json.dumps({"status": "error", "startup_error": reason,
                           "detail": "The Queryra API could not start."}).encode()
        await send({"type": "http.response.start", "status": 503,
                    "headers": [(b"content-type", b"application/json"), (b"cache-control", b"no-store")]})
        await send({"type": "http.response.body", "body": body})

    return fallback


try:
    from databeacon.api.main import app as _app
except Exception as _exc:  # noqa: BLE001
    import logging
    import traceback

    logging.getLogger("queryra").error("startup failed:\n%s", traceback.format_exc())
    try:
        from databeacon.diagnostics import describe

        _reason = describe(_exc)
    except Exception:  # noqa: BLE001
        _reason = type(_exc).__name__
    _app = _fallback_app(_reason)

app = _app
