"""Configurable reference lists (the in-app dropdowns).

Reference lists are CRUD-managed data, not hardcoded — the Data Integrity team
adds/renames/deactivates options through the "Manage lists" screen. Business
names, not ref_* technical labels (scoping skill §5).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExtraCol:
    name: str
    label: str
    help: str | None = None


@dataclass(frozen=True)
class ReferenceList:
    key: str          # matches FieldSpec.lookup and the Lakebase table name
    label: str
    table: str
    extra_cols: list[ExtraCol] = field(default_factory=list)
    note: str | None = None


REFERENCE_LISTS: list[ReferenceList] = [
    ReferenceList(
        key="supply_region",
        label="Supply Region",
        table="supply_region",
        extra_cols=[
            ExtraCol("description", "Description"),
            ExtraCol("region_code", "Region code", "e.g. NSW = 8201"),
        ],
        note="7-Eleven's supply territories (ESB, VIC, NSW, QLD, WA, FNQ).",
    ),
    ReferenceList(
        key="supply_method",
        label="Supply Method",
        table="supply_method",
        extra_cols=[
            ExtraCol("poc_topology", "POC topology", "direct = DSD · two-hop = via DC"),
        ],
        note="How the article reaches the store. Maps to the validation engine's "
             "Topology: Direct to Store (DSD) = direct, Via DC = two-hop.",
    ),
    ReferenceList(
        key="merchandise_category",
        label="Merchandise Category",
        table="merchandise_category",
        extra_cols=[],
        note="Retail/SAP article grouping (SAP MATKL). Fully user-editable.",
    ),
]

_BY_KEY = {r.key: r for r in REFERENCE_LISTS}


def get_reference_list(key: str) -> ReferenceList:
    return _BY_KEY[key]
