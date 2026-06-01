from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import User, Vehicle, TireEvent, VehicleCollaborator
from app.schemas import TireEventCreate, TireEventResponse
from app.auth import get_current_user

router = APIRouter()


def _check_vehicle_access(vehicle_id: int, user_id: int, db: Session) -> Vehicle:
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    is_owner = vehicle.user_id == user_id
    is_collab = db.query(VehicleCollaborator).filter(
        VehicleCollaborator.vehicle_id == vehicle_id,
        VehicleCollaborator.user_id == user_id,
    ).first() is not None
    if not (is_owner or is_collab):
        raise HTTPException(status_code=403, detail="Access denied")
    return vehicle


@router.get("/{vehicle_id}/events", response_model=List[TireEventResponse])
def list_tire_events(vehicle_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _check_vehicle_access(vehicle_id, current_user.id, db)
    return db.query(TireEvent).filter(TireEvent.vehicle_id == vehicle_id).order_by(TireEvent.date.desc()).all()


@router.post("/{vehicle_id}/events", response_model=TireEventResponse)
def create_tire_event(vehicle_id: int, data: TireEventCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _check_vehicle_access(vehicle_id, current_user.id, db)
    event = TireEvent(vehicle_id=vehicle_id, **data.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.put("/{vehicle_id}/events/{event_id}", response_model=TireEventResponse)
def update_tire_event(vehicle_id: int, event_id: int, data: TireEventCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _check_vehicle_access(vehicle_id, current_user.id, db)
    event = db.query(TireEvent).filter(TireEvent.id == event_id, TireEvent.vehicle_id == vehicle_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Tire event not found")
    for k, v in data.model_dump().items():
        setattr(event, k, v)
    db.commit()
    db.refresh(event)
    return event


@router.delete("/{vehicle_id}/events/{event_id}")
def delete_tire_event(vehicle_id: int, event_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _check_vehicle_access(vehicle_id, current_user.id, db)
    event = db.query(TireEvent).filter(TireEvent.id == event_id, TireEvent.vehicle_id == vehicle_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Tire event not found")
    db.delete(event)
    db.commit()
    return {"message": "Deleted"}
