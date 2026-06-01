from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timezone, timedelta
import urllib.parse
import httpx

from app.auth import get_current_user
from app.models import User, Vehicle
from app.database import get_db, SessionLocal
from app.data_config import get_config
from app.schemas import SmartcarExchangeRequest, SmartcarExchangeResponse, SmartcarVehicleInfo, SmartcarLinkRequest

router = APIRouter()

SMARTCAR_AUTH_URL = "https://connect.smartcar.com/oauth/authorize"
SMARTCAR_TOKEN_URL = "https://auth.smartcar.com/oauth/token"
SMARTCAR_API_BASE = "https://api.smartcar.com/v2.0"


def _smartcar_creds() -> tuple[str, str]:
    cfg = get_config().get("integrations", {})
    client_id = cfg.get("smartcar_client_id", "")
    client_secret = cfg.get("smartcar_client_secret", "")
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="Smartcar not configured — add client ID and secret in Settings → Integrations")
    return client_id, client_secret


def _check_vehicle(vehicle_id: int, user: User, db: Session) -> Vehicle:
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id, Vehicle.user_id == user.id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle


def _do_token_refresh(vehicle: Vehicle, client_id: str, client_secret: str, db: Session) -> Optional[str]:
    try:
        r = httpx.post(SMARTCAR_TOKEN_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": vehicle.smartcar_refresh_token,
        }, auth=(client_id, client_secret), timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()
        vehicle.smartcar_access_token = data["access_token"]
        vehicle.smartcar_refresh_token = data.get("refresh_token", vehicle.smartcar_refresh_token)
        vehicle.smartcar_token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=data.get("expires_in", 7200))
        db.commit()
        return data["access_token"]
    except Exception:
        return None


def sync_vehicle_odometer(vehicle: Vehicle, db: Session) -> Optional[float]:
    """Fetch odometer from Smartcar and update vehicle mileage. Returns miles or None on failure."""
    cfg = get_config().get("integrations", {})
    client_id = cfg.get("smartcar_client_id", "")
    client_secret = cfg.get("smartcar_client_secret", "")
    if not client_id or not client_secret:
        return None
    if not vehicle.smartcar_vehicle_id or not vehicle.smartcar_access_token:
        return None

    now = datetime.now(timezone.utc)
    access_token = vehicle.smartcar_access_token

    # Refresh if expired
    if vehicle.smartcar_token_expires_at:
        expires = vehicle.smartcar_token_expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= now:
            access_token = _do_token_refresh(vehicle, client_id, client_secret, db)
            if not access_token:
                return None

    headers = {"Authorization": f"Bearer {access_token}", "SC-Unit-System": "imperial"}
    try:
        r = httpx.get(f"{SMARTCAR_API_BASE}/vehicles/{vehicle.smartcar_vehicle_id}/odometer", headers=headers, timeout=15)
    except Exception:
        return None

    if r.status_code == 401:
        access_token = _do_token_refresh(vehicle, client_id, client_secret, db)
        if not access_token:
            return None
        headers["Authorization"] = f"Bearer {access_token}"
        try:
            r = httpx.get(f"{SMARTCAR_API_BASE}/vehicles/{vehicle.smartcar_vehicle_id}/odometer", headers=headers, timeout=15)
        except Exception:
            return None

    if r.status_code != 200:
        return None

    distance = r.json().get("distance")
    if distance is not None and distance > vehicle.current_mileage:
        vehicle.current_mileage = distance
    vehicle.smartcar_last_synced_at = now
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
    client_id, _ = _smartcar_creds()
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "read_vehicle_info read_odometer",
        "mode": "live",
    }
    url = f"{SMARTCAR_AUTH_URL}?{urllib.parse.urlencode(params)}"
    return {"url": url}


@router.post("/exchange", response_model=SmartcarExchangeResponse)
def exchange_code(body: SmartcarExchangeRequest, current_user: User = Depends(get_current_user)):
    client_id, client_secret = _smartcar_creds()

    r = httpx.post(SMARTCAR_TOKEN_URL, data={
        "grant_type": "authorization_code",
        "code": body.code,
        "redirect_uri": body.redirect_uri,
    }, auth=(client_id, client_secret), timeout=15)

    if r.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Smartcar token exchange failed: {r.text}")

    token_data = r.json()
    access_token = token_data["access_token"]
    refresh_token = token_data["refresh_token"]
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=token_data.get("expires_in", 7200))).isoformat()

    # List vehicles in this account
    vr = httpx.get(f"{SMARTCAR_API_BASE}/vehicles",
                   headers={"Authorization": f"Bearer {access_token}"}, timeout=15)
    if vr.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to list Smartcar vehicles")

    vehicle_ids = vr.json().get("vehicles", [])
    vehicles = []
    for vid in vehicle_ids:
        info = httpx.get(f"{SMARTCAR_API_BASE}/vehicles/{vid}",
                         headers={"Authorization": f"Bearer {access_token}"}, timeout=15)
        if info.status_code == 200:
            d = info.json()
            vehicles.append(SmartcarVehicleInfo(id=vid, make=d.get("make"), model=d.get("model"), year=d.get("year")))

    return SmartcarExchangeResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_expires_at=expires_at,
        vehicles=vehicles,
    )


@router.post("/link/{vehicle_id}")
def link_vehicle(vehicle_id: int, body: SmartcarLinkRequest,
                 db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    vehicle = _check_vehicle(vehicle_id, current_user, db)
    vehicle.smartcar_vehicle_id = body.smartcar_vehicle_id
    vehicle.smartcar_access_token = body.access_token
    vehicle.smartcar_refresh_token = body.refresh_token
    try:
        vehicle.smartcar_token_expires_at = datetime.fromisoformat(body.token_expires_at.replace("Z", "+00:00"))
    except Exception:
        vehicle.smartcar_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
    db.commit()
    return {"message": "Vehicle linked to Smartcar"}


@router.delete("/link/{vehicle_id}")
def unlink_vehicle(vehicle_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    vehicle = _check_vehicle(vehicle_id, current_user, db)
    vehicle.smartcar_vehicle_id = None
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
