# Article Master — MDM Control Plane

An operational **control plane** for maintaining 7-Eleven's Vendor → Supply-Region
authorisation master data. Built as a **React (Vite + TypeScript) frontend** on a
**FastAPI (Python) backend**, running on **Databricks Apps** and backed by
**Lakebase** (serverless Postgres). It is a POC/demo for the Article Master MDM
workstream and uses **synthetic data**.

The whole experience is a single surface: a live data grid with instant
search/filter, an in-place slide-over editor for add / edit / retire, and
**live validation** against the high-level variables (region, method, category)
as you type — no tab-hopping.

## Highlights

- **Single operational plane** — grid + slide-over editor; add/edit/retire never
  leave the screen or lose your filter context.
- **Live validation** — required fields, overlapping active windows on the
  business key, and coverage-gap signals evaluated server-side as you edit.
- **Derived status** — Active / Future / Expired computed from effective dates,
  which are **app-managed and hidden** from the user.
- **Change attribution** — every write stamps `updated_by` / `updated_at`,
  surfaced in-grid; the Lakebase→Delta CDC feed powers a downstream SCD Type 2
  history with a current-values materialized view.
- **Configurable dropdowns**, **CSV bulk load** with a validation preview, a
  read-only **activity log**, and **editor vs. administrator** roles.
- **Modular by config** — a new master-data domain is a registry entry, not new
  UI code.

## Layout

```
main.py              FastAPI app: REST API + serves the built SPA from static/
service.py           Business logic over the data layer (domain-agnostic)
auth.py              User + role from Databricks Apps forwarded headers
db/                  Lakebase connection, generic CRUD repository, schema + seed
core/                Status derivation + shared validators
domains/             Declarative domain registry (config-driven)
lookups/             Reference-list definitions (the configurable dropdowns)
static/              Built React SPA (checked in; the Apps deploy uploads it)
frontend/            React + Vite + TypeScript source (build -> ../static)
```

## Develop

```bash
# Backend (needs a Databricks profile with Lakebase access)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend (proxies /api to :8000)
cd frontend
npm install
npm run dev
```

`npm run build` emits the production SPA into `../static/`, which the backend
serves in production.

## Deploy (Databricks Apps)

```bash
cd frontend && npm run build && cd ..
databricks sync . <WORKSPACE_PATH> --profile <PROFILE>
databricks apps deploy mdm-control-plane --source-code-path <WORKSPACE_PATH> --profile <PROFILE>
```

The app's service principal connects to Lakebase via a short-lived OAuth token
and must have access to the target schema.

---

Demo/POC only. "7-Eleven", the 7-Eleven logo and related marks are trademarks of
their respective owners; not for external distribution.
