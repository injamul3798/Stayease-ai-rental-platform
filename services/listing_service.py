from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import Select, exists, or_, select
from sqlalchemy.orm import Session

from db.models import Booking, Listing


class ListingService:
    """Database-backed listing operations for search and detail retrieval."""

    ACTIVE_BOOKING_STATUSES = ("confirmed", "pending")

    def __init__(self, session: Session) -> None:
        self.session = session

    def search_available_properties(
        self,
        *,
        location: str,
        check_in: date,
        check_out: date,
        guest_count: int,
    ) -> dict[str, Any]:
        overlapping_booking = (
            select(Booking.id)
            .where(Booking.listing_id == Listing.id)
            .where(Booking.status.in_(self.ACTIVE_BOOKING_STATUSES))
            .where(Booking.check_in < check_out)
            .where(Booking.check_out > check_in)
        )

        statement: Select[tuple[Listing]] = (
            select(Listing)
            .where(Listing.is_active.is_(True))
            .where(Listing.max_guests >= guest_count)
            .where(or_(Listing.location.ilike(f"%{location}%"), Listing.area.ilike(f"%{location}%")))
            .where(~exists(overlapping_booking))
            .order_by(Listing.nightly_price_bdt.asc(), Listing.created_at.asc())
        )
        listings = list(self.session.scalars(statement))
        properties = [
            {
                "listing_id": listing.listing_code,
                "title": listing.title,
                "location": listing.location,
                "area": listing.area,
                "price_bdt": listing.nightly_price_bdt,
                "currency": "BDT",
                "max_guests": listing.max_guests,
                "available": True,
            }
            for listing in listings
        ]
        return {"properties": properties, "count": len(properties)}

    def get_listing_details(self, listing_code: str) -> dict[str, Any] | None:
        statement = select(Listing).where(Listing.listing_code == listing_code)
        listing = self.session.scalar(statement)
        if listing is None:
            return None
        return {
            "listing_id": listing.listing_code,
            "title": listing.title,
            "description": listing.description,
            "location": listing.location,
            "area": listing.area,
            "nightly_price_bdt": listing.nightly_price_bdt,
            "amenities": listing.amenities,
            "max_guests": listing.max_guests,
            "check_in_time": "14:00",
            "check_out_time": "11:00",
        }
