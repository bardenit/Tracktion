from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import User, TripEntry
from app.schemas import TripEntryCreate, TripEntryUpdate, TripEntryResponse, TripStats
from app.auth import get_current_user
from app.deps import check_vehicle_access

router = APIRouter()


@router.post("/{vehicle_id}/entries", response_model=TripEntryResponse)
def create_trip(
    vehicle_id: int,
    trip_data: TripEntryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db, require_write=True)
    trip = TripEntry(vehicle_id=vehicle_id, **trip_data.model_dump())
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


@router.get("/{vehicle_id}/entries", response_model=List[TripEntryResponse])
def list_trips(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db)
    return db.query(TripEntry).filter(TripEntry.vehicle_id == vehicle_id).order_by(TripEntry.date.desc()).all()


@router.put("/{vehicle_id}/entries/{trip_id}", response_model=TripEntryResponse)
def update_trip(
    vehicle_id: int,
    trip_id: int,
    trip_data: TripEntryUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db, require_write=True)
    trip = db.query(TripEntry).filter(TripEntry.id == trip_id, TripEntry.vehicle_id == vehicle_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    for field, value in trip_data.model_dump(exclude_unset=True).items():
        setattr(trip, field, value)

    db.commit()
    db.refresh(trip)
    return trip


@router.delete("/{vehicle_id}/entries/{trip_id}")
def delete_trip(
    vehicle_id: int,
    trip_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db, require_write=True)
    trip = db.query(TripEntry).filter(TripEntry.id == trip_id, TripEntry.vehicle_id == vehicle_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    db.delete(trip)
    db.commit()
    return {"message": "Trip deleted"}


@router.get("/{vehicle_id}/stats", response_model=TripStats)
def trip_stats(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db)
    total = db.query(func.sum(TripEntry.miles), func.count(TripEntry.id), func.max(TripEntry.date)) \
              .filter(TripEntry.vehicle_id == vehicle_id).first()
    return TripStats(
        total_miles=float(total[0] or 0),
        trip_count=int(total[1] or 0),
        last_trip_date=total[2],
    )
