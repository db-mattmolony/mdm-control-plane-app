"""One-off dev tool: convert the source spreadsheet into a committed seed CSV.

Source: ``LFLR Vendor Supply Region.XLSX`` (project root) — the real Vendor ->
Supply Region mapping 7-Eleven shared (columns: Vendor, Country Key, Supply region).

The business use case (per Supply Chain Ops) is an *article availability override*
keyed by (Article, Supply Region, Vendor). The source LFLR is **missing the Article
column**, so we synthesise a deterministic, plausible SAP-style article number per
(vendor, region) row — to be replaced when the real article source is wired in.

Produces, next to this file:
  - ``vendor_supply_region.csv`` : article, vendor_id, country_key, supply_region (one row per mapping)

There is no vendor-name source, so vendor names are left unset (the app keeps the
``vendor_name`` column nullable, to be populated from the SAP vendor master later).
The seed loader (``db/seed.py``) reads only this CSV at runtime — it never touches
the XLSX or openpyxl. Regenerate with:  ``python db/seed_data/build_seed.py``

Deterministic (stable hashing) so re-running is reproducible.
"""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import openpyxl

HERE = Path(__file__).resolve().parent
# <app root>/db/seed_data/build_seed.py -> the XLSX lives at the app/project root (2 up).
SOURCE = HERE.parents[1] / "LFLR Vendor Supply Region.XLSX"


def _synth_article(vendor: str, region: str) -> str:
    """Deterministic 5-digit SAP-style article number for a (vendor, region) row.

    Stable across runs (hashlib, not the salted built-in hash) so the committed
    CSV is reproducible. Placeholder until the real article source is provided.
    """
    h = hashlib.md5(f"{vendor}|{region}".encode()).hexdigest()
    return str(10000 + int(h, 16) % 90000)


def main() -> None:
    wb = openpyxl.load_workbook(SOURCE, read_only=True, data_only=True)
    ws = wb["Sheet1"]
    rows = [
        (_synth_article(str(v).strip(), str(r).strip()),
         str(v).strip(), str(c).strip(), str(r).strip())
        for v, c, r in ws.iter_rows(min_row=2, values_only=True)
        if v is not None and c is not None and r is not None
    ]

    mapping_csv = HERE / "vendor_supply_region.csv"
    with mapping_csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["article", "vendor_id", "country_key", "supply_region"])
        w.writerows(rows)

    print(f"Wrote {len(rows)} mappings -> {mapping_csv.name}")


if __name__ == "__main__":
    main()
