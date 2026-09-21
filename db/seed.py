"""Seed data — the Article Availability Override rows, from the LFLR 7-Eleven shared.

Loads the committed CSV in ``db/seed_data/`` (produced from
``LFLR Vendor Supply Region.XLSX`` by ``build_seed.py``):
  - ``vendor_supply_region.csv`` : the 8,658 (article, vendor, country, region) rows.
    ``article`` is synthetic (the LFLR was missing it — see build_seed.py).

There is no vendor-name source, so ``vendor_name`` is left unset (to be sourced
from the SAP vendor master later). Every seeded row starts as available_to_buy
"No"; users can change it in the app. The **Region dimension** (``supply_region``
reference list) is seeded from the distinct region codes in the mapping. Only
seeds a table when it is empty, so it never clobbers edits made in the app.
"""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from db import repository as repo

SEED_DIR = Path(__file__).resolve().parent / "seed_data"
MAPPING_CSV = SEED_DIR / "vendor_supply_region.csv"


def _read_mappings() -> list[dict]:
    with MAPPING_CSV.open(newline="") as f:
        return list(csv.DictReader(f))


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


def _seed_overrides(mappings: list[dict]) -> None:
    if repo.count("article_availability_override") > 0:
        return
    today = date.today()
    rows = [{
        "article": m["article"],
        "vendor_id": m["vendor_id"],
        "country_key": m["country_key"],
        "supply_region": m["supply_region"],
        "available_to_buy": "No",   # starting state; users can change it in the app
        "from_date": today,
        "to_date": None,
        "created_by": "seed@databricks",
        "updated_by": "seed@databricks",
    } for m in mappings]
    repo.bulk_insert("article_availability_override", rows)


def seed_all() -> None:
    mappings = _read_mappings()
    _seed_reference_lists(mappings)
    _seed_overrides(mappings)
