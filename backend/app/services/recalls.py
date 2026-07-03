import httpx
from typing import List, Optional

NHTSA_RECALLS_URL = "https://api.nhtsa.gov/recalls/recallsByVehicle"


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
