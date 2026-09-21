"""Schema bootstrap: create the schema + tables and seed synthetic data.

Runs once per app process (guarded at the caller). Because the deployed app's
service principal executes this, the SP owns the schema — which is exactly what
Lakebase requires for the app to read/write it (see databricks-lakebase skill,
"Schema Permissions for Deployed Apps"). Do NOT create this schema locally with
your own credentials before the app is deployed, or the SP loses ownership.
"""
from __future__ import annotations

from db.connection import SCHEMA, get_connection
from db.seed import seed_all

DDL = f"""
CREATE SCHEMA IF NOT EXISTS {SCHEMA};

CREATE TABLE IF NOT EXISTS {SCHEMA}.supply_region (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name         text UNIQUE NOT NULL,
    description  text,
    region_code  text,
    is_active    boolean NOT NULL DEFAULT true,
    sort_order   int NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS {SCHEMA}.article_availability_override (
    mapping_id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    article               text NOT NULL,
    vendor_id             text NOT NULL,
    vendor_name           text,
    country_key           text NOT NULL DEFAULT 'AU',
    supply_region         text NOT NULL,
    available_to_buy      text NOT NULL DEFAULT 'No',
    from_date             date NOT NULL,
    to_date               date,
    created_by            text,
    created_at            timestamptz NOT NULL DEFAULT now(),
    updated_by            text,
    updated_at            timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS {SCHEMA}.audit_log (
    audit_id     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    changed_at   timestamptz NOT NULL DEFAULT now(),
    changed_by   text,
    action       text NOT NULL,
    domain_key   text NOT NULL,
    record_pk    text,
    before_json  jsonb,
    after_json   jsonb
);
"""


def init_db() -> None:
    """Create schema/tables if missing, then seed reference + demo data if empty."""
    with get_connection() as conn:
        conn.execute(DDL)
        conn.commit()
    seed_all()
