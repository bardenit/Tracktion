from datetime import datetime
from typing import List, Optional, Set

import httpx

from app.database import SessionLocal
from app.models import Vehicle

NHTSA_RECALLS_URL = "https://api.nhtsa.gov/recalls/recallsByVehicle"

# Vehicles with a refresh already in flight, so a burst of dashboard loads
# does not stack duplicate NHTSA calls for the same vehicle.
_refreshing: Set[int] = set()


async def get_recalls(make: str, model: str, year: int) -> Optional[List[dict]]:
    """
    Fetch open recall campaigns for a vehicle from the NHTSA recalls API.

    Returns a list of recall dicts, or None if the lookup failed.
    """
    if not make or not model or not year:
        return None

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                NHTSA_RECALLS_URL,
                params={"make": make, "model": model, "modelYear": year},
                timeout=8.0,
            )
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError):
        return None

    recalls = []
    for item in data.get("results", []):
        recalls.append({
            "campaign_number": item.get("NHTSACampaignNumber"),
            "component": item.get("Component"),
            "summary": item.get("Summary"),
            "consequence": item.get("Consequence"),
            "remedy": item.get("Remedy"),
            "report_date": item.get("ReportReceivedDate"),
        })
    return recalls


async def refresh_recall_cache(vehicle_id: int) -> None:
    """Refresh a vehicle's recall cache out of band, with its own DB session."""
    if vehicle_id in _refreshing:
        return
    _refreshing.add(vehicle_id)
    db = SessionLocal()
    try:
        vehicle = db.get(Vehicle, vehicle_id)
        if vehicle is None or not vehicle.make or not vehicle.model or not vehicle.year:
            return
        make, model, year = vehicle.make, vehicle.model, vehicle.year
        db.close()

        recalls = await get_recalls(make, model, year)
        if recalls is None:
            return

        vehicle = db.get(Vehicle, vehicle_id)
        if vehicle is None:
            return
        vehicle.recalls_cache = {
            "campaigns": [{"campaign_number": r["campaign_number"], "component": r["component"]} for r in recalls],
            "checked_at": datetime.utcnow().isoformat(),
        }
        db.commit()
    finally:
        db.close()
        _refreshing.discard(vehicle_id)
