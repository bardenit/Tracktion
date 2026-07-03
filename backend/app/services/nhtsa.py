import re
from collections import Counter
from typing import List, Optional

import httpx

SAFETY_RATINGS_BASE = "https://api.nhtsa.gov/SafetyRatings"
COMPLAINTS_URL = "https://api.nhtsa.gov/complaints/complaintsByVehicle"
PRODUCTS_MODELS_URL = "https://api.nhtsa.gov/products/vehicle/models"
EPA_BASE = "https://www.fueleconomy.gov/ws/rest/vehicle"

TIMEOUT = 10.0


def _norm(s: Optional[str]) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def _drive_keywords(drive_type: Optional[str]) -> List[str]:
    d = (drive_type or "").lower()
    if "4" in d or "four" in d:
        return ["4WD", "4X4", "AWD"]
    if "all" in d:
        return ["AWD", "4WD"]
    if "front" in d:
        return ["FWD", "2WD"]
    if "rear" in d:
        return ["RWD", "2WD"]
    return []


def _pick_model(candidates: List[str], model: str, cab_type: Optional[str], fuel_type: Optional[str]) -> Optional[str]:
    """Pick the NHTSA variant name that best matches our vehicle."""
    nm = _norm(model)
    if not nm:
        return None
    matches = [c for c in candidates if _norm(c).startswith(nm) or nm in _norm(c)]
    if not matches:
        return None

    cab = (cab_type or "").lower()
    diesel = "diesel" in (fuel_type or "").lower()

    def score(c: str) -> tuple:
        cl = c.lower()
        s = 0
        if "crew" in cab and "crew" in cl:
            s += 2
        if ("super cab" in cab or "extended" in cab or "supercab" in cab.replace(" ", "")) and "supercab" in cl.replace(" ", ""):
            s += 2
        if "regular" in cab and "regular" in cl:
            s += 2
        if diesel == ("diesel" in cl):
            s += 1
        # Prefer shorter (more generic) names on ties
        return (-s, len(c))

    return sorted(matches, key=score)[0]


async def get_safety_ratings(
    make: str, model: str, year: int,
    drive_type: Optional[str] = None,
    cab_type: Optional[str] = None,
    fuel_type: Optional[str] = None,
) -> Optional[dict]:
    """NCAP crash-test ratings for the closest-matching vehicle configuration."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(f"{SAFETY_RATINGS_BASE}/modelyear/{year}/make/{make}")
            r.raise_for_status()
            candidates = [x.get("Model", "") for x in r.json().get("Results", [])]
            picked = _pick_model(candidates, model, cab_type, fuel_type)
            if not picked:
                return None

            r = await client.get(f"{SAFETY_RATINGS_BASE}/modelyear/{year}/make/{make}/model/{picked}")
            r.raise_for_status()
            variants = r.json().get("Results", [])
            if not variants:
                return None

            wanted = _drive_keywords(drive_type)
            chosen = variants[0]
            for v in variants:
                desc = (v.get("VehicleDescription") or "").upper()
                if any(k in desc for k in wanted):
                    chosen = v
                    break

            r = await client.get(f"{SAFETY_RATINGS_BASE}/VehicleId/{chosen['VehicleId']}")
            r.raise_for_status()
            results = r.json().get("Results", [])
            if not results:
                return None
            d = results[0]
    except (httpx.HTTPError, ValueError, KeyError):
        return None

    return {
        "vehicle_description": d.get("VehicleDescription"),
        "picture": d.get("VehiclePicture"),
        "overall": d.get("OverallRating"),
        "front_crash": d.get("OverallFrontCrashRating"),
        "side_crash": d.get("OverallSideCrashRating"),
        "side_pole": d.get("SidePoleCrashRating"),
        "rollover": d.get("RolloverRating"),
        "complaints_count": d.get("ComplaintsCount"),
        "recalls_count": d.get("RecallsCount"),
        "investigation_count": d.get("InvestigationCount"),
    }


async def get_complaints(
    make: str, model: str, year: int,
    cab_type: Optional[str] = None,
    fuel_type: Optional[str] = None,
) -> Optional[dict]:
    """Owner complaints filed with NHTSA, aggregated by component."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # NHTSA 400s on model names it doesn't know rather than returning empty
            r = await client.get(COMPLAINTS_URL, params={"make": make, "model": model, "modelYear": year})
            results = r.json().get("results", []) if r.status_code == 200 else []

            # Complaints DB often uses specific variant names (e.g. "F-150 SUPER CREW")
            if not results:
                r = await client.get(PRODUCTS_MODELS_URL, params={"modelYear": year, "make": make, "issueType": "c"})
                r.raise_for_status()
                candidates = list({x.get("model", "") for x in r.json().get("results", [])})
                picked = _pick_model(candidates, model, cab_type, fuel_type)
                if not picked:
                    return {"count": 0, "matched_model": None, "top_components": [], "crash_count": 0,
                            "fire_count": 0, "injury_count": 0, "recent": []}
                r = await client.get(COMPLAINTS_URL, params={"make": make, "model": picked, "modelYear": year})
                r.raise_for_status()
                results = r.json().get("results", [])
                model = picked
    except (httpx.HTTPError, ValueError):
        return None

    components = Counter()
    crash = fire = injuries = 0
    for c in results:
        comp = (c.get("components") or "UNKNOWN").split(",")[0].strip()
        components[comp] += 1
        if c.get("crash"):
            crash += 1
        if c.get("fire"):
            fire += 1
        injuries += c.get("numberOfInjuries") or 0

    def sort_key(c):
        return c.get("dateComplaintFiled") or c.get("dateOfIncident") or ""

    recent = []
    for c in sorted(results, key=sort_key, reverse=True)[:5]:
        summary = c.get("summary") or ""
        recent.append({
            "date": c.get("dateOfIncident") or c.get("dateComplaintFiled"),
            "component": (c.get("components") or "").split(",")[0].strip(),
            "summary": summary[:300] + ("…" if len(summary) > 300 else ""),
        })

    return {
        "count": len(results),
        "matched_model": model,
        "top_components": [{"component": k, "count": v} for k, v in components.most_common(6)],
        "crash_count": crash,
        "fire_count": fire,
        "injury_count": injuries,
        "recent": recent,
    }


def _menu_items(payload) -> List[dict]:
    # fueleconomy.gov returns an object instead of a list when there is one item
    items = payload.get("menuItem", [])
    if isinstance(items, dict):
        return [items]
    return items


async def get_epa_rating(
    make: str, model: str, year: int,
    drive_type: Optional[str] = None,
    displacement: Optional[float] = None,
    fuel_type: Optional[str] = None,
) -> Optional[dict]:
    """EPA window-sticker MPG for the closest-matching configuration."""
    headers = {"Accept": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, headers=headers) as client:
            r = await client.get(f"{EPA_BASE}/menu/model", params={"year": year, "make": make})
            r.raise_for_status()
            candidates = [i.get("value", "") for i in _menu_items(r.json())]

            nm = _norm(model)
            matches = [c for c in candidates if nm and nm in _norm(c)]
            if not matches:
                return None

            wanted = _drive_keywords(drive_type)
            diesel = "diesel" in (fuel_type or "").lower()

            def model_score(c: str) -> tuple:
                cu = c.upper()
                s = 0
                if any(k in cu for k in wanted):
                    s += 2
                if diesel == ("DIESEL" in cu):
                    s += 1
                return (-s, len(c))

            picked_model = sorted(matches, key=model_score)[0]

            r = await client.get(f"{EPA_BASE}/menu/options", params={"year": year, "make": make, "model": picked_model})
            r.raise_for_status()
            options = _menu_items(r.json())
            if not options:
                return None

            def option_score(o: dict) -> tuple:
                text = (o.get("text") or "").lower()
                s = 0
                if displacement is not None:
                    m = re.search(r"(\d+\.\d+)\s*l", text)
                    if m and abs(float(m.group(1)) - displacement) < 0.16:
                        s += 2
                if diesel == ("diesel" in text):
                    s += 1
                return -s

            picked_option = sorted(options, key=option_score)[0]

            r = await client.get(f"{EPA_BASE}/{picked_option['value']}")
            r.raise_for_status()
            d = r.json()
    except (httpx.HTTPError, ValueError, KeyError):
        return None

    def _num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    return {
        "matched_model": picked_model,
        "matched_option": picked_option.get("text"),
        "city": _num(d.get("city08")),
        "highway": _num(d.get("highway08")),
        "combined": _num(d.get("comb08")),
        "epa_fuel_type": d.get("fuelType1"),
    }
