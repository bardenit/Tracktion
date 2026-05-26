from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import User, Vehicle, TripEntry
from app.schemas import TripEntryCreate, TripEntryUpdate, TripEntryResponse, TripStats
from app.auth import get_current_user

router = APIRouter()


def get_vehicle_or_403(vehicle_id: int, user: User, db: Session) -> Vehicle:
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    if vehicle.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return vehicle


@router.post("/{vehicle_id}/entries", response_model=TripEntryResponse)
def create_trip(
    vehicle_id: int,
    trip_data: TripEntryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vehicle = get_vehicle_or_403(vehicle_id, current_user, db)
    trip = TripEntry(vehicle_id=vehicle_id, **trip_data.model_dump())
    db.add(trip)
    vehicle.current_mileage = (vehicle.current_mileage or 0) + trip_data.miles
    db.commit()
    db.refresh(trip)
    return trip


@router.get("/{vehicle_id}/entries", response_model=List[TripEntryResponse])
def list_trips(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_vehicle_or_403(vehicle_id, current_user, db)
    return db.query(TripEntry).filter(TripEntry.vehicle_id == vehicle_id).order_by(TripEntry.date.desc()).all()


@router.put("/{vehicle_id}/entries/{trip_id}", response_model=TripEntryResponse)
def update_trip(
    vehicle_id: int,
    trip_id: int,
    trip_data: TripEntryUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vehicle = get_vehicle_or_403(vehicle_id, current_user, db)
    trip = db.query(TripEntry).filter(TripEntry.id == trip_id, TripEntry.vehicle_id == vehicle_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    if trip_data.miles is not None and trip_data.miles != trip.miles:
        vehicle.current_mileage = (vehicle.current_mileage or 0) + (trip_data.miles - trip.miles)

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
    vehicle = get_vehicle_or_403(vehicle_id, current_user, db)
    trip = db.query(TripEntry).filter(TripEntry.id == trip_id, TripEntry.vehicle_id == vehicle_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    vehicle.current_mileage = max(0, (vehicle.current_mileage or 0) - trip.miles)
    db.delete(trip)
    db.commit()
    return {"message": "Trip deleted"}


@router.get("/{vehicle_id}/stats", response_model=TripStats)
def trip_stats(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_vehicle_or_403(vehicle_id, current_user, db)
    total = db.query(func.sum(TripEntry.miles), func.count(TripEntry.id), func.max(TripEntry.date)) \
              .filter(TripEntry.vehicle_id == vehicle_id).first()
    return TripStats(
        total_miles=float(total[0] or 0),
        trip_count=int(total[1] or 0),
        last_trip_date=total[2],
    )
