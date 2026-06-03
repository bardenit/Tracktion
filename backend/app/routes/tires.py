from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import User, TireEvent
from app.schemas import TireEventCreate, TireEventResponse
from app.auth import get_current_user
from app.deps import check_vehicle_access

router = APIRouter()


@router.get("/{vehicle_id}/events", response_model=List[TireEventResponse])
def list_tire_events(vehicle_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    check_vehicle_access(vehicle_id, current_user.id, db)
    return db.query(TireEvent).filter(TireEvent.vehicle_id == vehicle_id).order_by(TireEvent.date.desc()).all()


@router.post("/{vehicle_id}/events", response_model=TireEventResponse)
def create_tire_event(vehicle_id: int, data: TireEventCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    check_vehicle_access(vehicle_id, current_user.id, db, require_write=True)
    event = TireEvent(vehicle_id=vehicle_id, **data.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.put("/{vehicle_id}/events/{event_id}", response_model=TireEventResponse)
def update_tire_event(vehicle_id: int, event_id: int, data: TireEventCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    check_vehicle_access(vehicle_id, current_user.id, db, require_write=True)
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
    check_vehicle_access(vehicle_id, current_user.id, db, require_write=True)
    event = db.query(TireEvent).filter(TireEvent.id == event_id, TireEvent.vehicle_id == vehicle_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Tire event not found")
    db.delete(event)
    db.commit()
    return {"message": "Deleted"}
