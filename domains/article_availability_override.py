"""Seed domain: Article Availability Override.

The business use case (7-Eleven Supply Chain Ops): override an article's
"Available to buy in SAP" status for a given (Article, Supply Region, Vendor).
The business rule is that this table can **only ever override to "No"** — so the
value is app-set and locked, never entered by the user. This is the *first*
domain, not the app's purpose — it exists as config so the next domain is a
config change, not a rebuild.
"""
from __future__ import annotations

import os

from domains.config_types import DomainConfig, FieldSpec

# Governed Delta target for the (not-yet-built) Lakebase->UC sync. Catalog is
# env-driven so a new workspace only needs UC_CATALOG set (see app.yaml / DAB).
_CATALOG = os.environ.get("UC_CATALOG", "7_eleven_hackathon_catalog")

ARTICLE_AVAILABILITY_OVERRIDE = DomainConfig(
    key="article_availability_override",
    label="Article Availability Override",
    table="article_availability_override",
    pk="mapping_id",
    uc_target=f"{_CATALOG}.mdm.article_availability_override",
    fields=[
        FieldSpec("article", "Article", "text", help="SAP article number"),
        FieldSpec("vendor_id", "Vendor", "text", help="SAP vendor number"),
        FieldSpec("supply_region", "Supply Region", "lookup", lookup="supply_region"),
        # Availability override — user-configurable Yes/No (default No). Shown in
        # the grid and editable in the form.
        FieldSpec("available_to_buy", "Available to buy", "choice",
                  options=("Yes", "No")),
        # Vendor display name: not entered here and not shown — kept nullable in
        # the table to be populated from the SAP vendor master later.
        FieldSpec("vendor_name", "Vendor name", "text",
                  required=False, user_managed=False,
                  help="To be sourced from SAP vendor master later"),
        # Country key is carried from the source but not part of data entry.
        FieldSpec("country_key", "Country", "text", required=False, user_managed=False),
        # Effective dating is maintained by the app, not entered by the user:
        # from_date is set on creation, to_date is set when the row is retired.
        # These drive the derived status but are never shown or configured.
        FieldSpec("from_date", "Effective from", "date", user_managed=False),
        FieldSpec("to_date", "Effective to", "date", required=False, user_managed=False),
    ],
    # Grid mirrors the business table: Article | Supply Region | Vendor | Available to buy.
    list_columns=["article", "supply_region", "vendor_id", "available_to_buy"],
    search_fields=["article", "vendor_id"],
    filter_fields=["supply_region"],
    business_key=["article", "supply_region", "vendor_id"],
    # No coverage dimension: "coverage gaps" is a supply-coverage concept that
    # does not apply to an override-to-No table (a region with no override just
    # means nothing is blocked there).
    coverage_dimension=None,
)
