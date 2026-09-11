"""Current user + role, resolved from Databricks Apps forwarded headers.

Framework-agnostic (no Streamlit): callers pass the request headers in. Roles
(editor vs admin) will map to Unity Catalog groups in production; until those
groups are nominated (scoping skill §10) we resolve the role from an optional
MDM_ADMINS env var, and honour a demo "view as" override header so the two-role
behaviour (user story 9) can be shown end to end.
"""
from __future__ import annotations

import os
from typing import Mapping

EDITOR = "Editor"
ADMIN = "Administrator"

_USER_HEADERS = (
    "x-forwarded-email",
    "x-forwarded-preferred-username",
    "x-forwarded-user",
)


def current_user(headers: Mapping[str, str]) -> str:
    # Header lookups are case-insensitive on Starlette's Headers, but normalise
    # anyway so a plain dict works too.
    lower = {k.lower(): v for k, v in headers.items()}
    for key in _USER_HEADERS:
        if lower.get(key):
            return lower[key]
    return os.environ.get("MDM_FALLBACK_USER", "local-dev@databricks")


def _default_role(user: str) -> str:
    admins = [a.strip().lower() for a in os.environ.get("MDM_ADMINS", "").split(",") if a.strip()]
    # Demo default: with no admin list configured, everyone is an admin so all
    # features are visible. Tighten by setting MDM_ADMINS in production.
    if not admins:
        return ADMIN
    return ADMIN if user.lower() in admins else EDITOR


def effective_role(user: str, view_as: str | None) -> str:
    """Role in force, honouring the demo 'view as' override header."""
    if view_as in (EDITOR, ADMIN):
        return view_as
    return _default_role(user)


def is_admin(user: str, view_as: str | None) -> bool:
    return effective_role(user, view_as) == ADMIN
