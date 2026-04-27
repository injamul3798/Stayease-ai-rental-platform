from __future__ import annotations

import re
from datetime import date
from typing import Any


LOCATION_PATTERN = re.compile(r"\bin\s+([A-Za-z' -]+?)(?:\s+from|\s+for|$)", re.IGNORECASE)
DATE_RANGE_PATTERN = re.compile(r"\bfrom\s+(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})\b", re.IGNORECASE)
GUEST_COUNT_PATTERN = re.compile(r"\bfor\s+(\d+)\s+(?:guest|guests)\b", re.IGNORECASE)
LISTING_ID_PATTERN = re.compile(r"\b([A-Z]{2,5}-\d{2,5})\b")
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
NAME_PATTERN = re.compile(r"\bmy name is\s+([A-Za-z ]{2,80})", re.IGNORECASE)


def extract_search_params(message: str) -> dict[str, Any]:
    params: dict[str, Any] = {}
    location_match = LOCATION_PATTERN.search(message)
    date_range_match = DATE_RANGE_PATTERN.search(message)
    guest_count_match = GUEST_COUNT_PATTERN.search(message)

    if location_match:
        params["location"] = location_match.group(1).strip()
    if date_range_match:
        params["check_in"] = date.fromisoformat(date_range_match.group(1))
        params["check_out"] = date.fromisoformat(date_range_match.group(2))
    if guest_count_match:
        params["guest_count"] = int(guest_count_match.group(1))
    return params


def extract_listing_id(message: str) -> str | None:
    match = LISTING_ID_PATTERN.search(message.upper())
    return match.group(1) if match else None


def extract_booking_fields(message: str) -> dict[str, Any]:
    fields = extract_search_params(message)
    listing_id = extract_listing_id(message)
    email_match = EMAIL_PATTERN.search(message)
    name_match = NAME_PATTERN.search(message)

    if listing_id:
        fields["listing_id"] = listing_id
    if email_match:
        fields["guest_email"] = email_match.group(0)
    if name_match:
        fields["guest_name"] = name_match.group(1).strip()
    return fields
