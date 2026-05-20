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
                # Parse results from NHTSA response
                results = {item["Variable"]: item["Value"] for item in data["Results"]}
                
                # Extract relevant fields
                decode_data = VINDecodeResponse(
                    vin=vin,
                    make=results.get("Make"),
                    model=results.get("Model"),
                    year=int(results.get("ModelYear", 0)) if results.get("ModelYear") else None,
                    engine_hp=results.get("EngineHP"),
                    engine_cylinders=results.get("EngineCylinders"),
                    transmission_type=results.get("TransmissionType"),
                    drive_type=results.get("DriveType"),
                    fuel_type=results.get("FuelTypePrimary"),
                    doors=results.get("Doors"),
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
