from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
import hashlib
import json
from uuid import UUID

from app.models import User, FuelEntry, FuelIdempotencyOperation
from app.schemas import FuelEntryCreate, FuelEntryResponse, FuelEntryUpdate, FuelBulkImport, BulkImportResponse
from app.services.bulk_imports import begin_bulk_import, finish_bulk_import
from app.services.fuel_calculations import recalculate_fuel_economy, validate_fuel_entry_order
from app.services.vehicle_mileage import observe_vehicle_mileage
from app.auth import get_current_user
from app.deps import check_vehicle_access

router = APIRouter()


@router.post("/{vehicle_id}/entries/bulk", response_model=BulkImportResponse)
def import_fuel_entries(vehicle_id: int, batch: FuelBulkImport, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    check_vehicle_access(vehicle_id, current_user.id, db, require_write=True)
    operation_id, payload_hash, previous = begin_bulk_import(db, current_user.id, vehicle_id, "fuel", batch)
    if previous:
        return BulkImportResponse(operation_id=operation_id, imported_count=previous.imported_count)
    existing = db.query(FuelEntry).filter(FuelEntry.vehicle_id == vehicle_id).all()
    ordered = sorted(batch.entries, key=lambda item: (item.date, item.mileage))
    combined = list(existing)
    try:
        for item in ordered:
            validate_fuel_entry_order(combined, item.date, item.mileage)
            entry = FuelEntry(vehicle_id=vehicle_id, **item.model_dump(exclude={"operation_id"}))
            db.add(entry)
            db.flush()
            combined.append(entry)
        recalculate_vehicle_fuel_economy(vehicle_id, db)
        observe_vehicle_mileage(db, vehicle_id, max(item.mileage for item in ordered))
        finish_bulk_import(db, current_user.id, vehicle_id, "fuel", operation_id, payload_hash, len(ordered))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return BulkImportResponse(operation_id=operation_id, imported_count=len(ordered))


def recalculate_vehicle_fuel_economy(vehicle_id: int, db: Session) -> None:
    entries = (
        db.query(FuelEntry)
        .filter(FuelEntry.vehicle_id == vehicle_id)
        .order_by(FuelEntry.date.asc(), FuelEntry.mileage.asc(), FuelEntry.id.asc())
        .all()
    )
    recalculate_fuel_economy(entries)


@router.post("/{vehicle_id}/entries", response_model=FuelEntryResponse)
def create_fuel_entry(
    vehicle_id: int,
    entry_data: FuelEntryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vehicle = check_vehicle_access(vehicle_id, current_user.id, db, require_write=True)

    operation_id = entry_data.operation_id
    payload = entry_data.model_dump(mode="json", exclude={"operation_id"})
    payload_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if operation_id:
        try:
            operation_id = str(UUID(operation_id))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid operation ID") from exc
        previous = db.query(FuelIdempotencyOperation).filter(
            FuelIdempotencyOperation.user_id == current_user.id,
            FuelIdempotencyOperation.operation_id == operation_id,
        ).first()
        if previous:
            if previous.vehicle_id != vehicle_id or previous.payload_hash != payload_hash:
                raise HTTPException(status_code=409, detail="Idempotency operation conflict")
            return previous.fuel_entry

    entries = db.query(FuelEntry).filter(FuelEntry.vehicle_id == vehicle_id).all()
    try:
        validate_fuel_entry_order(entries, entry_data.date, entry_data.mileage)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    entry = FuelEntry(
        vehicle_id=vehicle_id,
        date=entry_data.date,
        mileage=entry_data.mileage,
        gallons=entry_data.gallons,
        cost=entry_data.cost,
        location=entry_data.location,
        notes=entry_data.notes,
        octane=entry_data.octane,
        missed_fillup=entry_data.missed_fillup,
        partial_fillup=entry_data.partial_fillup,
    )
    db.add(entry)
    db.flush()
    recalculate_vehicle_fuel_economy(vehicle_id, db)

    observe_vehicle_mileage(db, vehicle_id, entry_data.mileage)

    if operation_id:
        db.add(FuelIdempotencyOperation(
            user_id=current_user.id,
            operation_id=operation_id,
            vehicle_id=vehicle_id,
            payload_hash=payload_hash,
            fuel_entry_id=entry.id,
        ))

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
        .order_by(FuelEntry.date.desc(), FuelEntry.mileage.desc(), FuelEntry.id.desc())
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
    entry_data: FuelEntryUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vehicle = check_vehicle_access(vehicle_id, current_user.id, db, require_write=True)
    entry = db.query(FuelEntry).filter(FuelEntry.id == entry_id, FuelEntry.vehicle_id == vehicle_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Fuel entry not found")

    entries = db.query(FuelEntry).filter(FuelEntry.vehicle_id == vehicle_id).all()
    try:
        validate_fuel_entry_order(entries, entry_data.date, entry_data.mileage, exclude_id=entry.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    calculation_values = (
        entry.date,
        entry.mileage,
        entry.gallons,
        entry.cost,
        bool(entry.missed_fillup),
        bool(entry.partial_fillup),
    )
    entry.date = entry_data.date
    entry.mileage = entry_data.mileage
    entry.gallons = entry_data.gallons
    entry.cost = entry_data.cost
    entry.location = entry_data.location
    entry.notes = entry_data.notes
    entry.octane = entry_data.octane
    entry.missed_fillup = entry_data.missed_fillup
    partial_fillup = (
        entry_data.partial_fillup
        if "partial_fillup" in entry_data.model_fields_set
        else bool(entry.partial_fillup)
    )
    entry.partial_fillup = partial_fillup
    if calculation_values != (
        entry_data.date,
        entry_data.mileage,
        entry_data.gallons,
        entry_data.cost,
        entry_data.missed_fillup,
        partial_fillup,
    ):
        db.flush()
        recalculate_vehicle_fuel_economy(vehicle_id, db)

    observe_vehicle_mileage(db, vehicle_id, entry_data.mileage)

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
    check_vehicle_access(vehicle_id, current_user.id, db, require_write=True)
    entry = db.query(FuelEntry).filter(FuelEntry.id == entry_id, FuelEntry.vehicle_id == vehicle_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Fuel entry not found")
    db.delete(entry)
    db.flush()
    recalculate_vehicle_fuel_economy(vehicle_id, db)
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
        return {"average_mpg": None, "total_spent": 0, "total_gallons": 0, "entries_count": 0, "miles_per_day": None, "last_entry_date": None}

    miles_per_day = None
    dated = sorted(entries, key=lambda e: e.date)
    if len(dated) >= 2:
        days = (dated[-1].date - dated[0].date).days
        miles = dated[-1].mileage - dated[0].mileage
        if days > 0 and miles > 0:
            miles_per_day = miles / days

    ordered = sorted(entries, key=lambda e: (e.date, e.mileage, e.id))
    valid_miles, valid_gallons = recalculate_fuel_economy(ordered)
    return {
        "average_mpg": valid_miles / valid_gallons if valid_gallons else None,
        "total_spent": sum(e.cost for e in entries),
        "total_gallons": sum(e.gallons for e in entries),
        "entries_count": len(entries),
        "miles_per_day": miles_per_day,
        "last_entry_date": dated[-1].date.isoformat(),
    }
