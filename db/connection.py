"""Lakebase (Postgres) connectivity for the MDM app.

On Databricks Apps the platform injects PGHOST / PGDATABASE / PGUSER /
LAKEBASE_ENDPOINT when a `postgres` resource is attached to the app. We read
those, fall back to project constants + the SDK for local development, and
authenticate with a short-lived OAuth token that we cache and refresh before
its 1-hour expiry (see databricks-lakebase connectivity guide, Pattern 4).

Connections are opened per logical operation and closed immediately; list reads
are cached at the Streamlit layer, so connection churn stays low even though
Streamlit re-runs the script on every interaction.
"""
from __future__ import annotations

import os
import threading
import time
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

# --- Project fallbacks (used only when the platform env vars are absent) ------
PROJECT_ID = "mdm-article-master"
BRANCH = "production"
ENDPOINT_PATH = f"projects/{PROJECT_ID}/branches/{BRANCH}/endpoints/primary"
SCHEMA = "mdm"

_TOKEN_TTL = 3600          # Lakebase OAuth tokens last 1 hour
_TOKEN_REFRESH_MARGIN = 300  # refresh 5 min early
_CONNECT_RETRIES = 3       # scale-to-zero wake can drop the first attempt

_lock = threading.Lock()
_token_cache = {"value": None, "expires_at": 0.0}
_workspace_client = None


def _get_workspace_client():
    global _workspace_client
    if _workspace_client is None:
        from databricks.sdk import WorkspaceClient
        _workspace_client = WorkspaceClient()
    return _workspace_client


def _conn_params() -> dict:
    """Resolve connection parameters from injected env vars, else derive them."""
    endpoint = os.environ.get("LAKEBASE_ENDPOINT", ENDPOINT_PATH)
    host = os.environ.get("PGHOST")
    user = os.environ.get("PGUSER")
    dbname = os.environ.get("PGDATABASE", "databricks_postgres")

    if not host or not user:
        w = _get_workspace_client()
        if not host:
            host = w.postgres.get_endpoint(name=endpoint).status.hosts.host
        if not user:
            user = w.current_user.me().user_name

    return {
        "endpoint": endpoint,
        "host": host,
        "user": user,
        "dbname": dbname,
        "port": int(os.environ.get("PGPORT", "5432")),
        "sslmode": os.environ.get("PGSSLMODE", "require"),
    }


def _current_token(endpoint: str) -> str:
    with _lock:
        now = time.time()
        if _token_cache["value"] and now < _token_cache["expires_at"]:
            return _token_cache["value"]
        w = _get_workspace_client()
        cred = w.postgres.generate_database_credential(endpoint=endpoint)
        _token_cache["value"] = cred.token
        _token_cache["expires_at"] = now + _TOKEN_TTL - _TOKEN_REFRESH_MARGIN
        return cred.token


@contextmanager
def get_connection():
    """Yield a psycopg connection authenticated with a fresh OAuth token.

    Retries a few times so the first request after scale-to-zero (compute
    waking) does not surface as an error to the user.
    """
    params = _conn_params()
    last_err = None
    for attempt in range(_CONNECT_RETRIES):
        try:
            token = _current_token(params["endpoint"])
            conn = psycopg.connect(
                host=params["host"],
                port=params["port"],
                dbname=params["dbname"],
                user=params["user"],
                password=token,
                sslmode=params["sslmode"],
                connect_timeout=15,
                row_factory=dict_row,
            )
            try:
                yield conn
                return
            finally:
                conn.close()
        except psycopg.OperationalError as err:  # scale-to-zero / transient
            last_err = err
            # Force a token refresh on the next attempt in case it was auth.
            with _lock:
                _token_cache["expires_at"] = 0.0
            time.sleep(1.5 * (attempt + 1))
    raise last_err
