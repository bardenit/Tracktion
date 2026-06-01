from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timezone
import urllib.parse
import httpx

from app.auth import get_current_user
from app.models import User, Vehicle
from app.database import get_db, SessionLocal
from app.data_config import get_config
from app.schemas import SmartcarConnectRequest, SmartcarConnectResponse, SmartcarVehicleInfo, SmartcarLinkRequest

router = APIRouter()

SMARTCAR_AUTH_URL = "https://connect.smartcar.com/oauth/authorize"
SMARTCAR_TOKEN_URL = "https://iam.smartcar.com/oauth2/token"
SMARTCAR_API_BASE = "https://api.smartcar.com/v2.0"


def _smartcar_creds() -> tuple[str, str, str]:
    """Returns (app_id, m2m_client_id, m2m_secret). app_id is for Connect URL; m2m_* for token exchange."""
    cfg = get_config().get("integrations", {})
    app_id = cfg.get("smartcar_client_id", "")
    m2m_client_id = cfg.get("smartcar_m2m_client_id", "")
    m2m_secret = cfg.get("smartcar_client_secret", "")
    if not app_id:
        raise HTTPException(status_code=400, detail="Smartcar Application ID not configured — add it in Settings → Integrations")
    if not m2m_client_id or not m2m_secret:
        raise HTTPException(status_code=400, detail="Smartcar M2M credentials not configured — add Client ID and Secret in Settings → Integrations")
    return app_id, m2m_client_id, m2m_secret


def _get_app_token(m2m_client_id: str, m2m_secret: str) -> str:
    """Fetches a fresh application-level access token via client_credentials grant."""
    r = httpx.post(SMARTCAR_TOKEN_URL, data={
        "grant_type": "client_credentials",
        "client_id": m2m_client_id,
        "client_secret": m2m_secret,
    }, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=15)
    if r.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Smartcar token request failed: {r.text}")
    return r.json()["access_token"]


def _check_vehicle(vehicle_id: int, user: User, db: Session) -> Vehicle:
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id, Vehicle.user_id == user.id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle


def sync_vehicle_odometer(vehicle: Vehicle, db: Session) -> Optional[float]:
    """Fetch odometer from Smartcar and update vehicle mileage. Returns miles or None on failure."""
    cfg = get_config().get("integrations", {})
    m2m_client_id = cfg.get("smartcar_m2m_client_id", "")
    m2m_secret = cfg.get("smartcar_client_secret", "")
    if not m2m_client_id or not m2m_secret:
        return None
    if not vehicle.smartcar_vehicle_id or not vehicle.smartcar_user_id:
        return None

    try:
        access_token = _get_app_token(m2m_client_id, m2m_secret)
    except Exception:
        return None

    headers = {
        "Authorization": f"Bearer {access_token}",
        "SC-Unit-System": "imperial",
        "sc-user-id": vehicle.smartcar_user_id,
    }
    try:
        r = httpx.get(f"{SMARTCAR_API_BASE}/vehicles/{vehicle.smartcar_vehicle_id}/odometer", headers=headers, timeout=15)
    except Exception:
        return None

    if r.status_code != 200:
        return None

    distance = r.json().get("distance")
    if distance is not None and distance > vehicle.current_mileage:
        vehicle.current_mileage = distance
    vehicle.smartcar_last_synced_at = datetime.now(timezone.utc)
    db.commit()
    return distance


def run_daily_sync():
    """Called by the background task — syncs all linked vehicles."""
    db = SessionLocal()
    try:
        vehicles = db.query(Vehicle).filter(Vehicle.smartcar_vehicle_id.isnot(None)).all()
        for v in vehicles:
            try:
                sync_vehicle_odometer(v, db)
                print(f"Smartcar sync: vehicle {v.id} → {v.current_mileage} mi")
            except Exception as e:
                print(f"Smartcar sync error for vehicle {v.id}: {e}")
    finally:
        db.close()


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/auth-url")
def get_auth_url(redirect_uri: str, current_user: User = Depends(get_current_user)):
    app_id, _, _ = _smartcar_creds()
    params = {
        "response_type": "code",
        "client_id": app_id,
        "redirect_uri": redirect_uri,
        "scope": "read_vehicle_info read_odometer",
        "mode": "live",
    }
    url = f"{SMARTCAR_AUTH_URL}?{urllib.parse.urlencode(params)}"
    return {"url": url}


@router.post("/connect", response_model=SmartcarConnectResponse)
def connect_user(body: SmartcarConnectRequest, current_user: User = Depends(get_current_user)):
    """Called after OAuth redirect — receives Smartcar user_id, lists their vehicles."""
    _, m2m_client_id, m2m_secret = _smartcar_creds()
    access_token = _get_app_token(m2m_client_id, m2m_secret)

    headers = {
        "Authorization": f"Bearer {access_token}",
        "sc-user-id": body.user_id,
    }

    vr = httpx.get(f"{SMARTCAR_API_BASE}/vehicles", headers=headers, timeout=15)
    if vr.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Failed to list Smartcar vehicles: {vr.text}")

    vehicle_ids = vr.json().get("vehicles", [])
    vehicles = []
    for vid in vehicle_ids:
        info = httpx.get(f"{SMARTCAR_API_BASE}/vehicles/{vid}", headers=headers, timeout=15)
        if info.status_code == 200:
            d = info.json()
            vehicles.append(SmartcarVehicleInfo(id=vid, make=d.get("make"), model=d.get("model"), year=d.get("year")))

    return SmartcarConnectResponse(user_id=body.user_id, vehicles=vehicles)


@router.post("/link/{vehicle_id}")
def link_vehicle(vehicle_id: int, body: SmartcarLinkRequest,
                 db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    vehicle = _check_vehicle(vehicle_id, current_user, db)
    vehicle.smartcar_vehicle_id = body.smartcar_vehicle_id
    vehicle.smartcar_user_id = body.smartcar_user_id
    vehicle.smartcar_access_token = None
    vehicle.smartcar_refresh_token = None
    vehicle.smartcar_token_expires_at = None
    db.commit()
    return {"message": "Vehicle linked to Smartcar"}


@router.delete("/link/{vehicle_id}")
def unlink_vehicle(vehicle_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    vehicle = _check_vehicle(vehicle_id, current_user, db)
    vehicle.smartcar_vehicle_id = None
    vehicle.smartcar_user_id = None
    vehicle.smartcar_access_token = None
    vehicle.smartcar_refresh_token = None
    vehicle.smartcar_token_expires_at = None
    vehicle.smartcar_last_synced_at = None
    db.commit()
    return {"message": "Vehicle unlinked from Smartcar"}


@router.post("/sync/{vehicle_id}")
def sync_vehicle(vehicle_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    vehicle = _check_vehicle(vehicle_id, current_user, db)
    if not vehicle.smartcar_vehicle_id:
        raise HTTPException(status_code=400, detail="Vehicle is not linked to Smartcar")
    distance = sync_vehicle_odometer(vehicle, db)
    if distance is None:
        raise HTTPException(status_code=502, detail="Smartcar sync failed — check credentials or vehicle connection")
    return {
        "mileage": distance,
        "synced_at": vehicle.smartcar_last_synced_at.isoformat() if vehicle.smartcar_last_synced_at else None,
    }
