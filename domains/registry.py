"""The domain registry — the mechanism that makes the app modular.

A new master-data domain is onboarded by adding a DomainConfig entry here (plus
a Lakebase table). The generic CRUD renderer (views/crud_view.py) reads these
configs and produces the list / add / edit / retire screens with no UI changes.
"""
from __future__ import annotations

from domains.config_types import DomainConfig, FieldSpec  # noqa: F401 (re-exported)
from domains.article_availability_override import ARTICLE_AVAILABILITY_OVERRIDE

DOMAINS: list[DomainConfig] = [
    ARTICLE_AVAILABILITY_OVERRIDE,
    # Add future master-data domains here — config only, no UI changes.
]


def get_domain(key: str) -> DomainConfig:
    return next(d for d in DOMAINS if d.key == key)
