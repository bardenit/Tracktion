from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import User, FuelEntry
from app.schemas import FuelEntryCreate, FuelEntryResponse
from app.auth import get_current_user
from app.deps import check_vehicle_access

router = APIRouter()


@router.post("/{vehicle_id}/entries", response_model=FuelEntryResponse)
def create_fuel_entry(
    vehicle_id: int,
    entry_data: FuelEntryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vehicle = check_vehicle_access(vehicle_id, current_user.id, db)

    previous_entry = (
        db.query(FuelEntry)
        .filter(FuelEntry.vehicle_id == vehicle_id)
        .order_by(FuelEntry.date.desc())
        .first()
    )

    if previous_entry and entry_data.mileage <= previous_entry.mileage:
        raise HTTPException(
            status_code=400,
            detail=f"Mileage must be greater than your last fill-up at {int(previous_entry.mileage):,} mi",
        )

    mpg = None
    cost_per_mile = None
    if previous_entry:
        miles_driven = entry_data.mileage - previous_entry.mileage
        if miles_driven > 0:
            mpg = miles_driven / entry_data.gallons
            cost_per_mile = entry_data.cost / miles_driven

    entry = FuelEntry(
        vehicle_id=vehicle_id,
        date=entry_data.date,
        mileage=entry_data.mileage,
        gallons=entry_data.gallons,
        cost=entry_data.cost,
        location=entry_data.location,
        notes=entry_data.notes,
        octane=entry_data.octane,
        mpg=mpg,
        cost_per_mile=cost_per_mile,
    )
    db.add(entry)

    if entry_data.mileage > vehicle.current_mileage:
        vehicle.current_mileage = entry_data.mileage

    db.commit()
    db.refresh(entry)
    return entry


@router.get("/{vehicle_id}/entries", response_model=List[FuelEntryResponse])
def list_fuel_entries(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db)
    return (
        db.query(FuelEntry)
        .filter(FuelEntry.vehicle_id == vehicle_id)
        .order_by(FuelEntry.date.desc())
        .all()
    )


@router.get("/{vehicle_id}/entries/{entry_id}", response_model=FuelEntryResponse)
def get_fuel_entry(
    vehicle_id: int,
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db)
    entry = db.query(FuelEntry).filter(FuelEntry.id == entry_id, FuelEntry.vehicle_id == vehicle_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Fuel entry not found")
    return entry


@router.put("/{vehicle_id}/entries/{entry_id}", response_model=FuelEntryResponse)
def update_fuel_entry(
    vehicle_id: int,
    entry_id: int,
    entry_data: FuelEntryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vehicle = check_vehicle_access(vehicle_id, current_user.id, db)
    entry = db.query(FuelEntry).filter(FuelEntry.id == entry_id, FuelEntry.vehicle_id == vehicle_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Fuel entry not found")

    mpg = entry.mpg
    cost_per_mile = entry.cost_per_mile

    if entry.mileage != entry_data.mileage or entry.gallons != entry_data.gallons:
        previous_entry = (
            db.query(FuelEntry)
            .filter(FuelEntry.vehicle_id == vehicle_id, FuelEntry.date < entry_data.date)
            .order_by(FuelEntry.date.desc())
            .first()
        )
        mpg = None
        cost_per_mile = None
        if previous_entry:
            miles_driven = entry_data.mileage - previous_entry.mileage
            if miles_driven > 0:
                mpg = miles_driven / entry_data.gallons
                cost_per_mile = entry_data.cost / miles_driven

    entry.date = entry_data.date
    entry.mileage = entry_data.mileage
    entry.gallons = entry_data.gallons
    entry.cost = entry_data.cost
    entry.location = entry_data.location
    entry.notes = entry_data.notes
    entry.octane = entry_data.octane
    entry.mpg = mpg
    entry.cost_per_mile = cost_per_mile

    if entry_data.mileage > vehicle.current_mileage:
        vehicle.current_mileage = entry_data.mileage

    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{vehicle_id}/entries/{entry_id}")
def delete_fuel_entry(
    vehicle_id: int,
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db)
    entry = db.query(FuelEntry).filter(FuelEntry.id == entry_id, FuelEntry.vehicle_id == vehicle_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Fuel entry not found")
    db.delete(entry)
    db.commit()
    return {"message": "Fuel entry deleted"}


@router.get("/{vehicle_id}/stats")
def get_fuel_stats(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db)
    entries = db.query(FuelEntry).filter(FuelEntry.vehicle_id == vehicle_id).all()

    if not entries:
        return {"average_mpg": None, "total_spent": 0, "total_gallons": 0, "entries_count": 0}

    mpg_values = [e.mpg for e in entries if e.mpg is not None]
    return {
        "average_mpg": sum(mpg_values) / len(mpg_values) if mpg_values else None,
        "total_spent": sum(e.cost for e in entries),
        "total_gallons": sum(e.gallons for e in entries),
        "entries_count": len(entries),
    }
