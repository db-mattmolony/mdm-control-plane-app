"""Synthetic seed data for the demo.

Deterministic (fixed RNG seed) so re-seeding an empty DB is reproducible. Only
seeds a table when it is empty, so it never clobbers edits made in the app.
The data is illustrative — it mirrors the shape of what 7-Eleven will share, not
real supplier records.
"""
from __future__ import annotations

import random
from datetime import date, timedelta

from db import repository as repo

# --- Reference lists ----------------------------------------------------------
SUPPLY_REGIONS = [
    # name, description, region_code, default supply topology
    ("NSW", "New South Wales", "8201", "two-hop"),
    ("VIC", "Victoria", "8202", "two-hop"),
    ("QLD", "Queensland", "8203", "two-hop"),
    ("ESB", "Eastern Seaboard (shared DC network)", "8200", "two-hop"),
    ("WA", "Western Australia", "8204", "direct"),
    ("FNQ", "Far North Queensland", "8205", "direct"),
]

SUPPLY_METHODS = [
    # name, poc_topology
    ("Via Distribution Centre (DC)", "two-hop"),
    ("Direct to Store (DSD)", "direct"),
]

MERCHANDISE_CATEGORIES = [
    "Coffee & Hot Beverages",
    "Slurpee & Frozen Drinks",
    "Bakery & Pastries",
    "Hot Food To Go",
    "Cold Beverages",
    "Confectionery",
    "Snacks & Chips",
    "Dairy & Chilled",
    "Grocery & Ambient",
    "Ice & Frozen Goods",
    "Tobacco & Vaping",
]

# --- Vendors (synthetic; plausible AU suppliers) ------------------------------
VENDORS = [
    ("100014", "Patties Foods Pty Ltd", ["Bakery & Pastries", "Hot Food To Go"]),
    ("100027", "Coca-Cola Europacific Partners", ["Cold Beverages", "Slurpee & Frozen Drinks"]),
    ("100031", "Asahi Beverages", ["Cold Beverages"]),
    ("100042", "PepsiCo Australia", ["Cold Beverages", "Snacks & Chips"]),
    ("100055", "The Smith's Snackfood Co", ["Snacks & Chips"]),
    ("100063", "Mondelez Australia", ["Confectionery", "Snacks & Chips"]),
    ("100078", "Mars Wrigley Australia", ["Confectionery"]),
    ("100081", "Nestlé Australia", ["Confectionery", "Coffee & Hot Beverages"]),
    ("100094", "Lion Dairy & Drinks", ["Dairy & Chilled", "Cold Beverages"]),
    ("100102", "Bega Cheese Ltd", ["Dairy & Chilled"]),
    ("100119", "George Weston Foods (Tip Top)", ["Bakery & Pastries"]),
    ("100126", "Simplot Australia", ["Ice & Frozen Goods", "Hot Food To Go"]),
    ("100133", "Peters Ice Cream", ["Ice & Frozen Goods"]),
    ("100147", "Bulla Dairy Foods", ["Dairy & Chilled", "Ice & Frozen Goods"]),
    ("100158", "Arnott's Group", ["Snacks & Chips", "Confectionery"]),
    ("100166", "Fonterra Australia", ["Dairy & Chilled"]),
    ("100171", "Ferrero Australia", ["Confectionery"]),
    ("100189", "Grinders Coffee Roasters", ["Coffee & Hot Beverages"]),
    ("100194", "Vittoria Food & Beverage", ["Coffee & Hot Beverages"]),
    ("100203", "Philip Morris Limited", ["Tobacco & Vaping"]),
    ("100215", "British American Tobacco Australia", ["Tobacco & Vaping"]),
    ("100228", "Goodman Fielder", ["Grocery & Ambient", "Bakery & Pastries"]),
    ("100236", "Unilever Australia", ["Ice & Frozen Goods", "Grocery & Ambient"]),
    ("100249", "Sanitarium Health Food Co", ["Grocery & Ambient"]),
    ("100254", "Frucor Suntory", ["Cold Beverages"]),
]

DC_REGIONS = {"NSW", "VIC", "QLD", "ESB"}


def _seed_reference_lists() -> None:
    if repo.count("supply_region") == 0:
        for i, (name, desc, code, _topo) in enumerate(SUPPLY_REGIONS):
            repo.insert("supply_region", {
                "name": name, "description": desc, "region_code": code,
                "is_active": True, "sort_order": i,
            })
    if repo.count("supply_method") == 0:
        for i, (name, topo) in enumerate(SUPPLY_METHODS):
            repo.insert("supply_method", {
                "name": name, "poc_topology": topo, "is_active": True, "sort_order": i,
            })
    if repo.count("merchandise_category") == 0:
        for i, name in enumerate(MERCHANDISE_CATEGORIES):
            repo.insert("merchandise_category", {
                "name": name, "is_active": True, "sort_order": i,
            })


def _seed_authorisations() -> None:
    if repo.count("vendor_supply_authorisation") > 0:
        return

    rng = random.Random(20260911)
    today = date.today()
    regions = [r[0] for r in SUPPLY_REGIONS]

    dc = "Via Distribution Centre (DC)"
    dsd = "Direct to Store (DSD)"

    rows: list[dict] = []
    for vendor_id, vendor_name, categories in VENDORS:
        # Each vendor supplies a subset of regions for each of its categories.
        for category in categories:
            chosen_regions = rng.sample(regions, k=rng.randint(3, len(regions)))
            for region in chosen_regions:
                method = dc if region in DC_REGIONS else dsd
                # Occasionally a DC region is served direct (real-world variation).
                if region in DC_REGIONS and rng.random() < 0.12:
                    method = dsd

                # Spread effective dates so Active / Expired / Future all appear.
                roll = rng.random()
                if roll < 0.72:            # Active (started, open or future end)
                    frm = today - timedelta(days=rng.randint(60, 900))
                    to = None if rng.random() < 0.6 else today + timedelta(days=rng.randint(30, 720))
                elif roll < 0.9:           # Expired
                    frm = today - timedelta(days=rng.randint(400, 1200))
                    to = today - timedelta(days=rng.randint(5, 250))
                else:                      # Future
                    frm = today + timedelta(days=rng.randint(10, 180))
                    to = None if rng.random() < 0.5 else frm + timedelta(days=rng.randint(180, 720))

                rows.append({
                    "vendor_id": vendor_id,
                    "vendor_name": vendor_name,
                    "supply_region": region,
                    "supply_method": method,
                    "merchandise_category": category,
                    "from_date": frm,
                    "to_date": to,
                    "created_by": "seed@databricks",
                    "updated_by": "seed@databricks",
                })

    for row in rows:
        repo.insert("vendor_supply_authorisation", row)


def seed_all() -> None:
    _seed_reference_lists()
    _seed_authorisations()
