"""One-off dev tool: convert the source spreadsheet into committed seed CSVs.

Source: ``LFLR Vendor Supply Region.XLSX`` (project root) — the real Vendor ->
Supply Region mapping 7-Eleven shared (columns: Vendor, Country Key, Supply region).

Produces, next to this file:
  - ``vendor_supply_region.csv`` : vendor_id, country_key, supply_region (one row per mapping)
  - ``vendor_names.csv``         : vendor_id, vendor_name (deterministic synthetic)

The source has no vendor-name column, so names are synthetic/plausible for the
POC and will be replaced when a real vendor-name source is wired in. The seed
loader (``db/seed.py``) reads only these CSVs at runtime — it never touches the
XLSX or openpyxl. Regenerate with:  ``python db/seed_data/build_seed.py``

Deterministic (fixed RNG seed) so re-running is reproducible.
"""
from __future__ import annotations

import csv
import random
from pathlib import Path

import openpyxl

HERE = Path(__file__).resolve().parent
# <root>/MDM Application/<app>/db/seed_data/build_seed.py -> project root is 4 up.
SOURCE = HERE.parents[3] / "LFLR Vendor Supply Region.XLSX"

# --- Deterministic synthetic AU supplier-name generator ----------------------
_PREFIX = [
    "Southern Cross", "Great Southern", "Coastal", "Sunstate", "Redgum",
    "Harbourside", "Tablelands", "Riverina", "Golden Plains", "Bass Strait",
    "Darling", "Kanga", "Boomerang", "Outback", "Emu Plains", "Wattle",
    "Blue Gum", "Sandstone", "Coral Coast", "Alpine", "Macquarie", "Fremantle",
    "Yarra Valley", "Barossa", "Daintree", "Kimberley", "Nullarbor", "Tasman",
    "Gippsland", "Hunter Valley", "Snowy", "Pilbara", "Kakadu", "Esperance",
]
_CORE = [
    "Foods", "Beverages", "Dairy", "Snackfoods", "Fresh Produce", "Provisions",
    "Confectionery", "Bakeries", "Meats", "Grocery", "Trading", "Distribution",
    "Wholesale", "Brands", "Pantry", "Harvest", "Coffee Roasters", "Frozen",
]
_SUFFIX = [
    "Pty Ltd", "Australia", "Group", "Co", "& Sons", "Holdings", "Industries",
    "Australasia", "Enterprises", "Supply Co",
]


def _make_name(rng: random.Random) -> str:
    return f"{rng.choice(_PREFIX)} {rng.choice(_CORE)} {rng.choice(_SUFFIX)}"


def main() -> None:
    wb = openpyxl.load_workbook(SOURCE, read_only=True, data_only=True)
    ws = wb["Sheet1"]
    rows = [
        (str(v).strip(), str(c).strip(), str(r).strip())
        for v, c, r in ws.iter_rows(min_row=2, values_only=True)
        if v is not None and c is not None and r is not None
    ]

    mapping_csv = HERE / "vendor_supply_region.csv"
    with mapping_csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["vendor_id", "country_key", "supply_region"])
        w.writerows(rows)

    vendors = sorted({r[0] for r in rows}, key=lambda x: (len(x), x))
    rng = random.Random(20260917)
    used: set[str] = set()
    names_csv = HERE / "vendor_names.csv"
    with names_csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["vendor_id", "vendor_name"])
        for vid in vendors:
            name = _make_name(rng)
            while name in used:
                name = _make_name(rng)
            used.add(name)
            w.writerow([vid, name])

    print(f"Wrote {len(rows)} mappings -> {mapping_csv.name}")
    print(f"Wrote {len(vendors)} vendor names -> {names_csv.name}")


if __name__ == "__main__":
    main()
