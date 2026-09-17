"""Seed data — the real Vendor -> Supply Region mapping 7-Eleven shared.

Loads the committed CSVs in ``db/seed_data/`` (produced from
``LFLR Vendor Supply Region.XLSX`` by ``build_seed.py``):
  - ``vendor_supply_region.csv`` : the 8,658 vendor -> region mappings (vendor_id,
    country_key, supply_region)
  - ``vendor_names.csv``         : a synthetic vendor name per vendor_id (the source
    has no name column; to be sourced from SAP vendor master later)

The **Region dimension** (``supply_region`` reference list) is seeded from the
distinct region codes in the mapping. Only seeds a table when it is empty, so it
never clobbers edits made in the app.
"""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from db import repository as repo

SEED_DIR = Path(__file__).resolve().parent / "seed_data"
MAPPING_CSV = SEED_DIR / "vendor_supply_region.csv"
NAMES_CSV = SEED_DIR / "vendor_names.csv"


def _read_mappings() -> list[dict]:
    with MAPPING_CSV.open(newline="") as f:
        return list(csv.DictReader(f))


def _read_names() -> dict[str, str]:
    with NAMES_CSV.open(newline="") as f:
        return {r["vendor_id"]: r["vendor_name"] for r in csv.DictReader(f)}


def _seed_reference_lists(mappings: list[dict]) -> None:
    # Region dimension: distinct supply-region codes, ordered numerically where possible.
    if repo.count("supply_region") == 0:
        codes = sorted({m["supply_region"] for m in mappings},
                       key=lambda c: (0, int(c)) if c.isdigit() else (1, c))
        for i, code in enumerate(codes):
            repo.insert("supply_region", {
                "name": code, "description": None, "region_code": code,
                "is_active": True, "sort_order": i,
            })


def _seed_authorisations(mappings: list[dict], names: dict[str, str]) -> None:
    if repo.count("vendor_supply_authorisation") > 0:
        return
    today = date.today()
    rows = [{
        "vendor_id": m["vendor_id"],
        "vendor_name": names.get(m["vendor_id"], m["vendor_id"]),
        "country_key": m["country_key"],
        "supply_region": m["supply_region"],
        "from_date": today,
        "to_date": None,
        "created_by": "seed@databricks",
        "updated_by": "seed@databricks",
    } for m in mappings]
    repo.bulk_insert("vendor_supply_authorisation", rows)


def seed_all() -> None:
    mappings = _read_mappings()
    names = _read_names()
    _seed_reference_lists(mappings)
    _seed_authorisations(mappings, names)
