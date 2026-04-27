from __future__ import annotations

from datetime import date
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, EmailStr, Field

from db.session import get_session_factory
from services.booking_service import BookingConflictError, BookingService, BookingValidationError
from services.listing_service import ListingService


class SearchAvailablePropertiesInput(BaseModel):
    location: str = Field(..., description="Bangladeshi city or area, such as Cox's Bazar or Dhanmondi.")
    check_in: date = Field(..., description="Stay start date in ISO format.")
    check_out: date = Field(..., description="Stay end date in ISO format.")
    guest_count: int = Field(..., ge=1, le=16, description="Total number of guests.")


class GetListingDetailsInput(BaseModel):
    listing_id: str = Field(..., description="Listing code (e.g., SEA-201) or property name.")


class CreateBookingInput(BaseModel):
    listing_id: str = Field(..., description="Listing code (e.g., SEA-201) or property name chosen by the guest.")
    check_in: date = Field(..., description="Booking start date in ISO format.")
    check_out: date = Field(..., description="Booking end date in ISO format.")
    guest_count: int = Field(..., ge=1, le=16, description="Total number of guests.")
    guest_name: str = Field(..., min_length=2, description="Guest full name.")
    guest_email: EmailStr = Field(..., description="Guest contact email.")


@tool(args_schema=SearchAvailablePropertiesInput)
def search_available_properties(
    location: str,
    check_in: date,
    check_out: date,
    guest_count: int,
) -> dict[str, Any]:
    """Return available properties for a location, date range, and guest count."""
    session = get_session_factory()()
    try:
        listing_service = ListingService(session=session)
        result = listing_service.search_available_properties(
            location=location,
            check_in=check_in,
            check_out=check_out,
            guest_count=guest_count,
        )
        result["check_in"] = check_in.isoformat()
        result["check_out"] = check_out.isoformat()
        result["guest_count"] = guest_count
        return result
    finally:
        session.close()


@tool(args_schema=GetListingDetailsInput)
def get_listing_details(listing_id: str) -> dict[str, Any]:
    """Return one listing's details for display to the guest."""
    session = get_session_factory()()
    try:
        listing_service = ListingService(session=session)
        result = listing_service.get_listing_details(listing_id)
        if result is None:
            return {"status": "error", "error": "listing not found", "listing_id": listing_id}
        return result
    finally:
        session.close()


@tool(args_schema=CreateBookingInput)
def create_booking(
    listing_id: str,
    check_in: date,
    check_out: date,
    guest_count: int,
    guest_name: str,
    guest_email: EmailStr,
) -> dict[str, Any]:
    """Create a booking after the guest confirms the stay."""
    session = get_session_factory()()
    try:
        booking_service = BookingService(session=session)
        return booking_service.create_booking(
            listing_code=listing_id,
            check_in=check_in,
            check_out=check_out,
            guest_count=guest_count,
            guest_name=guest_name,
            guest_email=str(guest_email),
        )
    except (BookingConflictError, BookingValidationError) as error:
        return {"status": "error", "error": str(error), "listing_id": listing_id}
    finally:
        session.close()
