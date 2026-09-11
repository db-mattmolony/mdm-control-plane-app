"""Effective-dating status — always derived, never stored (scoping skill §5)."""
from __future__ import annotations

from datetime import date


def derive_status(from_date, to_date, today: date | None = None) -> str:
    today = today or date.today()
    if from_date and from_date > today:
        return "Future"
    if to_date and to_date < today:
        return "Expired"
    return "Active"


def is_active(from_date, to_date, today: date | None = None) -> bool:
    return derive_status(from_date, to_date, today) == "Active"
