"""Declarative config types for a master-data domain.

Kept separate from the registry so each domain module can import them without a
circular dependency.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FieldSpec:
    name: str
    label: str
    kind: str = "text"            # text | date | lookup | choice
    required: bool = True
    lookup: str | None = None     # reference-list key when kind == "lookup"
    options: tuple[str, ...] | None = None  # fixed options when kind == "choice"
    help: str | None = None
    in_list: bool = True          # show in the browse table
    editable: bool = True         # editable on the edit form
    user_managed: bool = True     # False = maintained by the app, never shown/entered


@dataclass(frozen=True)
class DomainConfig:
    key: str                      # stable id
    label: str                    # human label (nav, headings)
    table: str                    # Lakebase table
    pk: str                       # surrogate primary key column
    fields: list[FieldSpec]
    list_columns: list[str]
    search_fields: list[str] = field(default_factory=list)
    filter_fields: list[str] = field(default_factory=list)
    business_key: list[str] = field(default_factory=list)  # uniqueness of active window
    soft_delete: bool = True      # retire by expiring, never hard-delete
    coverage_dimension: str | None = None  # e.g. supply_region -> flag "Missing" gaps
    uc_target: str | None = None  # governed Delta target (for the sync step)

    def get_field(self, name: str) -> FieldSpec | None:
        return next((f for f in self.fields if f.name == name), None)
