"""Seed domain: Vendor Supply Authorisation.

The vendor -> supply-region authorisation mapping that the SOS validation engine
reads. This is the *first* domain, not the app's purpose — it exists as config so
the next domain is a config change, not a rebuild.
"""
from __future__ import annotations

from domains.config_types import DomainConfig, FieldSpec

VENDOR_SUPPLY_AUTHORISATION = DomainConfig(
    key="vendor_supply_authorisation",
    label="Vendor Supply Authorisation",
    table="vendor_supply_authorisation",
    pk="mapping_id",
    uc_target="7_eleven_hackathon_catalog.mdm.vendor_supply_authorisation",
    fields=[
        FieldSpec("vendor_id", "Vendor ID", "text", help="SAP vendor number"),
        FieldSpec("vendor_name", "Vendor name", "text"),
        FieldSpec("supply_region", "Supply Region", "lookup", lookup="supply_region"),
        FieldSpec("supply_method", "Supply Method", "lookup", lookup="supply_method"),
        FieldSpec("merchandise_category", "Merchandise Category", "lookup",
                  lookup="merchandise_category"),
        # Effective dating is maintained by the app, not entered by the user:
        # from_date is set on creation, to_date is set when the row is retired.
        # These drive the derived status but are never shown or configured.
        FieldSpec("from_date", "Effective from", "date", user_managed=False),
        FieldSpec("to_date", "Effective to", "date", required=False, user_managed=False),
    ],
    list_columns=[
        "mapping_id", "vendor_id", "vendor_name", "supply_region",
        "supply_method", "merchandise_category", "status",
        "updated_by", "updated_at",
    ],
    search_fields=["vendor_id", "vendor_name"],
    filter_fields=["supply_region", "supply_method", "merchandise_category"],
    business_key=["vendor_id", "supply_region", "merchandise_category"],
    coverage_dimension="supply_region",
)
