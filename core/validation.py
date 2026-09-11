"""Shared validators for domain records. Returns a list of plain-English errors."""
from __future__ import annotations

from datetime import date


def validate_record(domain, values: dict, existing_rows: list[dict],
                    pk_value=None) -> list[str]:
    errors: list[str] = []

    # Required fields
    for field in domain.fields:
        if field.required and not values.get(field.name):
            errors.append(f"{field.label} is required.")

    # Effective dating: from_date <= to_date
    frm = values.get("from_date")
    to = values.get("to_date")
    if frm and to and isinstance(frm, date) and isinstance(to, date) and to < frm:
        errors.append("Effective to date cannot be before the effective from date.")

    # Overlapping active window for the same business key
    if domain.business_key and not errors:
        key = tuple(values.get(k) for k in domain.business_key)
        for row in existing_rows:
            if pk_value is not None and row.get(domain.pk) == pk_value:
                continue
            if tuple(row.get(k) for k in domain.business_key) != key:
                continue
            if _overlaps(frm, to, row.get("from_date"), row.get("to_date")):
                label = " / ".join(str(v) for v in key)
                errors.append(
                    f"An overlapping authorisation already exists for {label}. "
                    "Edit or retire that one instead of creating a duplicate."
                )
                break

    return errors


def _overlaps(a_from, a_to, b_from, b_to) -> bool:
    """Do two [from, to] windows overlap? Open-ended (None) = infinity."""
    a_to = a_to or date.max
    b_to = b_to or date.max
    if not a_from or not b_from:
        return False
    return a_from <= b_to and b_from <= a_to
