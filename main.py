"""FastAPI backend for the 7-Eleven Article Master control plane.

Serves a REST API over the reused Lakebase data layer and hosts the built React
SPA as static files. The schema + synthetic seed are created lazily on first
request by the app's service principal (which therefore owns the schema — see
databricks-lakebase, "Schema Permissions for Deployed Apps"). When this app
reuses a schema another app's SP already owns, the owner grants this SP access;
the lazy init below is then an idempotent no-op.
"""
from __future__ import annotations

import threading
import traceback
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import auth
import service

app = FastAPI(title="7-Eleven Article Master — Control Plane", docs_url=None, redoc_url=None)

_STATIC_DIR = Path(__file__).parent / "static"

# --- lazy DB bootstrap (runs once) -------------------------------------------
_db_lock = threading.Lock()
_db_ready = False
_db_error: str | None = None


def _ensure_db() -> None:
    global _db_ready, _db_error
    if _db_ready:
        return
    with _db_lock:
        if _db_ready:
            return
        try:
            from db.schema import init_db
            init_db()
            _db_ready = True
            _db_error = None
        except Exception as exc:  # noqa: BLE001 — surface a friendly error, don't crash
            _db_error = f"{type(exc).__name__}: {exc}"
            traceback.print_exc()
            raise HTTPException(
                status_code=503,
                detail="The database is starting up or unavailable. "
                       "If this persists, the app service principal may need access "
                       "to the Lakebase schema.",
            )


# --- identity ----------------------------------------------------------------
class Identity:
    def __init__(self, request: Request):
        self.user = auth.current_user(request.headers)
        self.view_as = request.headers.get("x-view-as-role")
        self.role = auth.effective_role(self.user, self.view_as)
        self.is_admin = auth.is_admin(self.user, self.view_as)


def identity(request: Request) -> Identity:
    return Identity(request)


def require_admin(ident: Identity) -> None:
    if not ident.is_admin:
        raise HTTPException(status_code=403, detail="Administrator role required.")


# --- request models ----------------------------------------------------------
class ValuesIn(BaseModel):
    values: dict


class ValidateIn(BaseModel):
    values: dict
    pk_value: int | None = None


class ReferenceOptionIn(BaseModel):
    data: dict


class BulkIn(BaseModel):
    rows: list[dict]


# --- API ----------------------------------------------------------------------
@app.get("/api/me")
def api_me(ident: Identity = Depends(identity)):
    return {"user": ident.user, "role": ident.role, "is_admin": ident.is_admin,
            "roles": [auth.EDITOR, auth.ADMIN]}


@app.get("/api/bootstrap")
def api_bootstrap(ident: Identity = Depends(identity)):
    _ensure_db()
    data = service.bootstrap()
    data["me"] = {"user": ident.user, "role": ident.role, "is_admin": ident.is_admin,
                  "roles": [auth.EDITOR, auth.ADMIN]}
    return data


@app.get("/api/authorisations")
def api_list(ident: Identity = Depends(identity)):
    _ensure_db()
    return {"rows": service.list_authorisations(), "coverage": service.coverage()}


@app.post("/api/validate")
def api_validate(body: ValidateIn, ident: Identity = Depends(identity)):
    _ensure_db()
    return service.validate(body.values, body.pk_value)


@app.post("/api/authorisations")
def api_create(body: ValuesIn, ident: Identity = Depends(identity)):
    _ensure_db()
    result = service.create(body.values, ident.user)
    return JSONResponse(result, status_code=200 if result["ok"] else 422)


@app.put("/api/authorisations/{pk}")
def api_update(pk: int, body: ValuesIn, ident: Identity = Depends(identity)):
    _ensure_db()
    result = service.update(pk, body.values, ident.user)
    return JSONResponse(result, status_code=200 if result["ok"] else 422)


@app.post("/api/authorisations/{pk}/retire")
def api_retire(pk: int, ident: Identity = Depends(identity)):
    _ensure_db()
    result = service.retire(pk, ident.user)
    return JSONResponse(result, status_code=200 if result["ok"] else 422)


@app.get("/api/audit")
def api_audit(ident: Identity = Depends(identity)):
    _ensure_db()
    return {"rows": service.audit()}


@app.get("/api/reference/{key}")
def api_reference(key: str, ident: Identity = Depends(identity)):
    _ensure_db()
    try:
        return service.list_reference(key)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown reference list.")


@app.post("/api/reference/{key}")
def api_reference_add(key: str, body: ReferenceOptionIn, ident: Identity = Depends(identity)):
    _ensure_db()
    require_admin(ident)
    result = service.add_reference_option(key, body.data, ident.user)
    return JSONResponse(result, status_code=200 if result["ok"] else 422)


@app.put("/api/reference/{key}/{opt_id}")
def api_reference_update(key: str, opt_id: int, body: ReferenceOptionIn,
                         ident: Identity = Depends(identity)):
    _ensure_db()
    require_admin(ident)
    result = service.update_reference_option(key, opt_id, body.data, ident.user)
    return JSONResponse(result, status_code=200 if result["ok"] else 422)


@app.post("/api/bulk/validate")
def api_bulk_validate(body: BulkIn, ident: Identity = Depends(identity)):
    _ensure_db()
    require_admin(ident)
    return service.bulk_validate(body.rows)


@app.post("/api/bulk/commit")
def api_bulk_commit(body: BulkIn, ident: Identity = Depends(identity)):
    _ensure_db()
    require_admin(ident)
    result = service.bulk_commit(body.rows, ident.user)
    return JSONResponse(result, status_code=200 if result["ok"] else 422)


@app.get("/api/health")
def api_health():
    return {"status": "ok", "db_ready": _db_ready, "db_error": _db_error}


# --- static SPA (registered last so /api/* wins) -----------------------------
if _STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")
