from __future__ import annotations

import json
from pathlib import Path
import sys

from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from db.models import Listing
from db.session import SessionLocal, init_db


def seed_listings() -> None:
    """Load sample StayEase listings into Postgres."""
    init_db()
    seed_path = ROOT_DIR / "seed_data" / "listings.json"
    listings = json.loads(seed_path.read_text(encoding="utf-8"))

    session = SessionLocal()
    try:
        for item in listings:
            existing = session.scalar(select(Listing).where(Listing.listing_code == item["listing_code"]))
            if existing is None:
                session.add(Listing(**item))
                continue

            existing.title = item["title"]
            existing.description = item["description"]
            existing.location = item["location"]
            existing.area = item["area"]
            existing.nightly_price_bdt = item["nightly_price_bdt"]
            existing.max_guests = item["max_guests"]
            existing.amenities = item["amenities"]
            existing.is_active = item["is_active"]

        session.commit()
    finally:
        session.close()


if __name__ == "__main__":
    seed_listings()
