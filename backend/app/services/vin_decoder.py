import httpx
from typing import Optional
from app.schemas import VINDecodeResponse

NHTSA_API_BASE = "https://vpic.nhtsa.dot.gov/api/vehicles"


async def decode_vin(vin: str) -> Optional[VINDecodeResponse]:
    """
    Decode a VIN using NHTSA vPIC API
    
    Args:
        vin: 17-character vehicle identification number
        
    Returns:
        VINDecodeResponse with decoded vehicle information or None if decode fails
    """
    
    if not vin or len(vin) != 17:
        return None
    
    url = f"{NHTSA_API_BASE}/DecodeVin/{vin}?format=json"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=5.0)
            response.raise_for_status()
            data = response.json()
            
            if data.get("Results"):
                # Keep first non-null value for each variable (NHTSA can return duplicates)
                results = {}
                for item in data["Results"]:
                    key = item["Variable"]
                    val = item["Value"]
                    if key not in results and val and val != "Not Applicable":
                        results[key] = val
                
                # Extract relevant fields
                raw_year = results.get("Model Year")
                decode_data = VINDecodeResponse(
                    vin=vin,
                    make=results.get("Make"),
                    model=results.get("Model"),
                    year=int(raw_year) if raw_year and raw_year.isdigit() else None,
                    # Engine
                    engine_model=results.get("Engine Model"),
                    engine_cylinders=results.get("Engine Number of Cylinders"),
                    engine_displacement_l=results.get("Displacement (L)"),
                    engine_hp=results.get("Engine Brake (hp) From"),
                    turbo=results.get("Turbo"),
                    fuel_type=results.get("Fuel Type - Primary"),
                    # Drivetrain
                    transmission_type=results.get("Transmission Style"),
                    transmission_speeds=results.get("Transmission Speeds"),
                    drive_type=results.get("Drive Type"),
                    # Body
                    body_class=results.get("Body Class"),
                    cab_type=results.get("Cab Type"),
                    doors=results.get("Doors"),
                    # Trim / identity
                    series=results.get("Series"),
                    trim=results.get("Trim"),
                    gvwr=results.get("Gross Vehicle Weight Rating From"),
                    # Origin
                    plant_city=results.get("Plant City"),
                    plant_country=results.get("Plant Country"),
                )
                
                return decode_data
    except (httpx.HTTPError, KeyError, ValueError):
        pass
    
    return None


def extract_vin_data_for_storage(decode_response: VINDecodeResponse) -> dict:
    """
    Convert VINDecodeResponse to JSON-serializable dict for database storage
    
    Args:
        decode_response: VINDecodeResponse object
        
    Returns:
        Dictionary suitable for storing in database JSON field
    """
    return decode_response.model_dump(exclude_none=True)
