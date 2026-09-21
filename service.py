"""Business logic for the operational control plane.

Thin layer over the reused data access (`db.repository`), validators
(`core.validation`), status derivation (`core.status`) and the domain registry
(`domains.registry`). Everything here is domain-agnostic and JSON-serialisable —
the FastAPI layer just exposes it, and a new master-data domain remains a config
change, not new code.

Effective dates are app-managed and hidden: from_date is set on creation,
to_date on retire. They drive the derived status server-side but are never sent
to the client. Every write stamps updated_by / updated_at for change attribution
and the downstream SCD Type 2 feed.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from core.status import derive_status
from core.validation import validate_record
from db import repository as repo
from domains.registry import DOMAINS, get_domain
from lookups.reference_lists import REFERENCE_LISTS, get_reference_list

# The control plane currently drives a single domain; keep it registry-resolved
# so onboarding the next domain is still config-only.
DOMAIN = DOMAINS[0]

# Columns we never expose to the client (effective dating is abstracted away).
_HIDDEN = {"from_date", "to_date"}


# --- serialisation -----------------------------------------------------------
def _iso(v: Any) -> Any:
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return v


def _public_row(row: dict) -> dict:
    """Add derived status, drop hidden effective dates, JSON-ify the rest."""
    status = derive_status(row.get("from_date"), row.get("to_date"))
    out = {k: _iso(v) for k, v in row.items() if k not in _HIDDEN}
    out["status"] = status
    return out


# --- field / domain descriptors ----------------------------------------------
def _field_descriptor(f) -> dict:
    return {
        "name": f.name,
        "label": f.label,
        "kind": f.kind,
        "required": f.required,
        "lookup": f.lookup,
        "options": list(f.options) if f.options else None,
        "help": f.help,
        "user_managed": f.user_managed,
    }


def _domain_descriptor(domain) -> dict:
    return {
        "key": domain.key,
        "label": domain.label,
        "uc_target": domain.uc_target,
        "pk": domain.pk,
        "fields": [_field_descriptor(f) for f in domain.fields if f.user_managed],
        "list_columns": [c for c in domain.list_columns if c not in _HIDDEN],
        "search_fields": domain.search_fields,
        "filter_fields": domain.filter_fields,
        "business_key": domain.business_key,
        "coverage_dimension": domain.coverage_dimension,
    }


def _lookup_options(key: str, active_only: bool = True) -> list[str]:
    rows = repo.fetch_all(key, order_by="sort_order, name")
    return [r["name"] for r in rows if (r.get("is_active") or not active_only)]


# --- read APIs ---------------------------------------------------------------
def bootstrap() -> dict:
    """Everything the SPA needs to render once: domain shape + dropdown options."""
    lookups = {
        rl.key: _lookup_options(rl.key, active_only=True) for rl in REFERENCE_LISTS
    }
    return {
        "domain": _domain_descriptor(DOMAIN),
        "lookups": lookups,
        "reference_lists": [
            {"key": rl.key, "label": rl.label, "note": rl.note,
             "extra_cols": [{"name": c.name, "label": c.label, "help": c.help}
                            for c in rl.extra_cols]}
            for rl in REFERENCE_LISTS
        ],
    }


def list_authorisations() -> list[dict]:
    rows = repo.fetch_all(DOMAIN.table, order_by="updated_at DESC NULLS LAST, mapping_id")
    return [_public_row(r) for r in rows]


def coverage() -> dict:
    """Regions (coverage dimension) with no active authorisation — the Hot Pie gap."""
    dim = DOMAIN.coverage_dimension
    if not dim:
        return {"dimension": None, "all": [], "covered": [], "gaps": []}
    all_values = _lookup_options(dim, active_only=True)
    rows = repo.fetch_all(DOMAIN.table)
    covered = sorted({
        r[dim] for r in rows
        if derive_status(r.get("from_date"), r.get("to_date")) == "Active"
    })
    gaps = [v for v in all_values if v not in covered]
    return {"dimension": dim, "all": all_values, "covered": covered, "gaps": gaps}


def audit(limit: int = 500) -> list[dict]:
    rows = repo.fetch_all("audit_log", order_by="changed_at DESC")
    return [{k: _iso(v) for k, v in r.items()} for r in rows[:limit]]


def list_reference(key: str) -> dict:
    rl = get_reference_list(key)
    rows = repo.fetch_all(rl.table, order_by="sort_order, name")
    return {
        "key": rl.key,
        "label": rl.label,
        "note": rl.note,
        "extra_cols": [{"name": c.name, "label": c.label, "help": c.help} for c in rl.extra_cols],
        "options": [{k: _iso(v) for k, v in r.items()} for r in rows],
    }


# --- validation ---------------------------------------------------------------
def _coverage_flag(values: dict) -> dict:
    """Does this record fill a currently-uncovered coverage dimension value?"""
    dim = DOMAIN.coverage_dimension
    if not dim or not values.get(dim):
        return {"fills_gap": False, "dimension": dim, "value": values.get(dim)}
    gap = values[dim] in coverage()["gaps"]
    return {"fills_gap": gap, "dimension": dim, "value": values[dim]}


def validate(values: dict, pk_value: Any = None) -> dict:
    """Live validation against the high-level variables. Returns plain-English
    errors plus a positive coverage signal so the UI can guide the user."""
    # App-managed dates for the overlap check (unchanged by add/edit).
    existing = repo.fetch_all(DOMAIN.table)
    probe = dict(values)
    if pk_value is not None:
        current = repo.get_one(DOMAIN.table, DOMAIN.pk, pk_value)
        probe.setdefault("from_date", current.get("from_date") if current else date.today())
        probe.setdefault("to_date", current.get("to_date") if current else None)
    else:
        probe.setdefault("from_date", date.today())
        probe.setdefault("to_date", None)
    errors = validate_record(DOMAIN, probe, existing, pk_value=pk_value)
    return {"errors": errors, "coverage": _coverage_flag(values)}


# --- writes -------------------------------------------------------------------
def _clean(values: dict) -> dict:
    """Keep only user-managed fields, stripped."""
    allowed = {f.name for f in DOMAIN.fields if f.user_managed}
    out = {}
    for k, v in values.items():
        if k not in allowed:
            continue
        out[k] = v.strip() if isinstance(v, str) else v
    return out


def _jsonable(d: dict) -> dict:
    return {k: _iso(v) for k, v in d.items()}


def create(values: dict, user: str) -> dict:
    vals = _clean(values)
    vals.setdefault("available_to_buy", "No")   # default when omitted
    vals["from_date"] = date.today()   # app-managed, hidden
    vals["to_date"] = None
    existing = repo.fetch_all(DOMAIN.table)
    errors = validate_record(DOMAIN, vals, existing)
    if errors:
        return {"ok": False, "errors": errors}
    payload = dict(vals)
    payload["created_by"] = user
    payload["updated_by"] = user
    payload["updated_at"] = datetime.utcnow()
    new_id = repo.insert(DOMAIN.table, payload, returning=DOMAIN.pk)
    repo.write_audit(user, "INSERT", DOMAIN.key, new_id, None, _jsonable(payload))
    return {"ok": True, "row": _public_row(repo.get_one(DOMAIN.table, DOMAIN.pk, new_id))}


def update(pk_value: Any, values: dict, user: str) -> dict:
    current = repo.get_one(DOMAIN.table, DOMAIN.pk, pk_value)
    if not current:
        return {"ok": False, "errors": ["Record not found."]}
    vals = _clean(values)
    # Effective dates unchanged by an edit; carry through for the overlap check.
    vals["from_date"] = current.get("from_date")
    vals["to_date"] = current.get("to_date")
    existing = repo.fetch_all(DOMAIN.table)
    errors = validate_record(DOMAIN, vals, existing, pk_value=pk_value)
    if errors:
        return {"ok": False, "errors": errors}
    payload = dict(vals)
    payload["updated_by"] = user
    payload["updated_at"] = datetime.utcnow()
    repo.update(DOMAIN.table, DOMAIN.pk, pk_value, payload)
    repo.write_audit(user, "UPDATE", DOMAIN.key, pk_value,
                     _jsonable(current), _jsonable(payload))
    return {"ok": True, "row": _public_row(repo.get_one(DOMAIN.table, DOMAIN.pk, pk_value))}


def retire(pk_value: Any, user: str) -> dict:
    current = repo.get_one(DOMAIN.table, DOMAIN.pk, pk_value)
    if not current:
        return {"ok": False, "errors": ["Record not found."]}
    today = date.today()
    payload = {"to_date": today, "updated_by": user, "updated_at": datetime.utcnow()}
    repo.update(DOMAIN.table, DOMAIN.pk, pk_value, payload)
    repo.write_audit(user, "RETIRE", DOMAIN.key, pk_value,
                     _jsonable(current), _jsonable({**current, **payload}))
    return {"ok": True, "row": _public_row(repo.get_one(DOMAIN.table, DOMAIN.pk, pk_value))}


# --- reference-list admin -----------------------------------------------------
def add_reference_option(key: str, data: dict, user: str) -> dict:
    rl = get_reference_list(key)
    name = (data.get("name") or "").strip()
    if not name:
        return {"ok": False, "errors": ["Name is required."]}
    existing = {r["name"].lower() for r in repo.fetch_all(rl.table)}
    if name.lower() in existing:
        return {"ok": False, "errors": [f"“{name}” already exists."]}
    row = {"name": name, "is_active": True,
           "sort_order": repo.count(rl.table)}
    for c in rl.extra_cols:
        if data.get(c.name) is not None:
            row[c.name] = data[c.name]
    new_id = repo.insert(rl.table, row, returning="id")
    repo.write_audit(user, "REF_INSERT", key, new_id, None, _jsonable(row))
    return {"ok": True}


def update_reference_option(key: str, opt_id: int, data: dict, user: str) -> dict:
    rl = get_reference_list(key)
    current = repo.get_one(rl.table, "id", opt_id)
    if not current:
        return {"ok": False, "errors": ["Option not found."]}
    allowed = {"name", "is_active", "sort_order"} | {c.name for c in rl.extra_cols}
    payload = {k: v for k, v in data.items() if k in allowed}
    if not payload:
        return {"ok": False, "errors": ["Nothing to update."]}
    repo.update(rl.table, "id", opt_id, payload)
    repo.write_audit(user, "REF_UPDATE", key, opt_id,
                     _jsonable(current), _jsonable({**current, **payload}))
    return {"ok": True}


# --- bulk load ----------------------------------------------------------------
def bulk_validate(rows: list[dict]) -> dict:
    user_fields = [f.name for f in DOMAIN.fields if f.user_managed]
    existing = repo.fetch_all(DOMAIN.table)
    today = date.today()
    problems: list[dict] = []
    parsed: list[dict] = []
    for i, raw in enumerate(rows):
        vals = {f: (raw.get(f) if raw.get(f) not in ("", None) else None) for f in user_fields}
        vals["from_date"] = today
        vals["to_date"] = None
        errs = validate_record(DOMAIN, vals, existing + parsed)
        if errs:
            problems.append({"row": i + 1, "errors": errs})
        else:
            parsed.append(vals)
    return {"valid": len(parsed), "total": len(rows), "problems": problems,
            "expected_columns": user_fields}


def bulk_commit(rows: list[dict], user: str) -> dict:
    check = bulk_validate(rows)
    if check["problems"]:
        return {"ok": False, "errors": ["Fix all row problems before committing."],
                "problems": check["problems"]}
    user_fields = [f.name for f in DOMAIN.fields if f.user_managed]
    today = date.today()
    committed = 0
    for raw in rows:
        payload = {f: (raw.get(f) if raw.get(f) not in ("", None) else None) for f in user_fields}
        payload["from_date"] = today
        payload["to_date"] = None
        payload["created_by"] = user
        payload["updated_by"] = user
        payload["updated_at"] = datetime.utcnow()
        new_id = repo.insert(DOMAIN.table, payload, returning=DOMAIN.pk)
        repo.write_audit(user, "BULK_INSERT", DOMAIN.key, new_id, None, _jsonable(payload))
        committed += 1
    return {"ok": True, "committed": committed}
