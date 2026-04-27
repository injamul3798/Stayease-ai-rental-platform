from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from db.models import Booking, Listing
from services.listing_service import ListingService


class BookingConflictError(Exception):
    """Raised when the requested stay dates are no longer available."""


class BookingValidationError(Exception):
    """Raised when booking input is incomplete or invalid."""


class BookingService:
    """Create bookings against Postgres with availability checks."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.listing_service = ListingService(session)

    def create_booking(
        self,
        *,
        listing_code: str,
        check_in: date,
        check_out: date,
        guest_count: int,
        guest_name: str,
        guest_email: str,
    ) -> dict[str, object]:
        if check_out <= check_in:
            raise BookingValidationError("check_out must be after check_in")

        listing = self.session.scalar(
            select(Listing).where(
                or_(
                    Listing.listing_code == listing_code,
                    Listing.title.ilike(f"%{listing_code}%"),
                )
            )
        )
        if listing is None:
            raise BookingValidationError("listing not found")

        resolved_listing_code = listing.listing_code

        if guest_count > listing.max_guests:
            raise BookingValidationError("guest_count exceeds listing capacity")

        search_result = self.listing_service.search_available_properties(
            location=listing.location,
            check_in=check_in,
            check_out=check_out,
            guest_count=guest_count,
        )
        available_codes = {item["listing_id"] for item in search_result["properties"]}
        if resolved_listing_code not in available_codes:
            raise BookingConflictError("listing is not available for the requested dates")

        total_nights = (check_out - check_in).days
        booking = Booking(
            booking_code=self._generate_booking_code(),
            listing_id=listing.id,
            guest_name=guest_name,
            guest_email=guest_email,
            guest_count=guest_count,
            check_in=check_in,
            check_out=check_out,
            total_price_bdt=listing.nightly_price_bdt * total_nights,
            status="confirmed",
        )
        self.session.add(booking)
        self.session.commit()
        self.session.refresh(booking)

        return {
            "booking_id": booking.booking_code,
            "status": booking.status,
            "listing_id": resolved_listing_code,
            "total_price_bdt": booking.total_price_bdt,
            "currency": "BDT",
        }

    @staticmethod
    def _generate_booking_code() -> str:
        return f"BK-{uuid.uuid4().hex[:10].upper()}"
