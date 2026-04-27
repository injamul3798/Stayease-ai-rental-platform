from __future__ import annotations

from datetime import date
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, EmailStr, Field


class SearchAvailablePropertiesInput(BaseModel):
    location: str = Field(..., description="Bangladeshi city or area, such as Cox's Bazar or Dhanmondi.")
    check_in: date = Field(..., description="Stay start date in ISO format.")
    check_out: date = Field(..., description="Stay end date in ISO format.")
    guest_count: int = Field(..., ge=1, le=16, description="Total number of guests.")


class GetListingDetailsInput(BaseModel):
    listing_id: str = Field(..., description="Stable listing identifier such as SEA-201.")


class CreateBookingInput(BaseModel):
    listing_id: str = Field(..., description="Listing identifier chosen by the guest.")
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
    return {
        "properties": [
            {
                "listing_id": "SEA-201",
                "title": "Beach View Studio",
                "location": location,
                "price_bdt": 6800,
                "currency": "BDT",
                "max_guests": 2,
                "available": True,
            },
            {
                "listing_id": "SEA-318",
                "title": "Kolatoli Family Suite",
                "location": location,
                "price_bdt": 8500,
                "currency": "BDT",
                "max_guests": 4,
                "available": True,
            },
        ],
        "count": 2,
        "check_in": check_in.isoformat(),
        "check_out": check_out.isoformat(),
        "guest_count": guest_count,
    }


@tool(args_schema=GetListingDetailsInput)
def get_listing_details(listing_id: str) -> dict[str, Any]:
    """Return one listing's details for display to the guest."""
    return {
        "listing_id": listing_id,
        "title": "Beach View Studio",
        "description": "A clean studio near the sea beach with balcony access.",
        "location": "Cox's Bazar",
        "nightly_price_bdt": 6800,
        "amenities": ["WiFi", "AC", "Hot Water", "Breakfast"],
        "max_guests": 2,
        "check_in_time": "14:00",
        "check_out_time": "11:00",
    }


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
    return {
        "booking_id": "BK-20260514-0001",
        "status": "confirmed",
        "listing_id": listing_id,
        "guest_name": guest_name,
        "guest_email": str(guest_email),
        "guest_count": guest_count,
        "check_in": check_in.isoformat(),
        "check_out": check_out.isoformat(),
        "total_price_bdt": 13600,
        "currency": "BDT",
    }
