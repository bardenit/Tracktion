import hashlib
import json
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import User, MaintenanceEntry, MaintenanceReminder, MaintenanceCompletionOperation
from app.schemas import (
    MaintenanceEntryCreate,
    MaintenanceEntryResponse,
    MaintenanceReminderCreate,
    MaintenanceReminderUpdate,
    MaintenanceReminderResponse,
    MaintenanceCompletionCreate,
)
from app.auth import get_current_user
from app.deps import check_vehicle_access
from app.services.maintenance_reminders import recompute_reminders
from app.services.vehicle_mileage import observe_vehicle_mileage

router = APIRouter()


@router.post("/{vehicle_id}/entries", response_model=MaintenanceEntryResponse)
def create_maintenance_entry(
    vehicle_id: int,
    entry_data: MaintenanceEntryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db, require_write=True)

    entry = MaintenanceEntry(
        vehicle_id=vehicle_id,
        date=entry_data.date,
        mileage=entry_data.mileage,
        type=entry_data.type,
        cost=entry_data.cost,
        service_provider=entry_data.service_provider,
        notes=entry_data.notes,
    )
    db.add(entry)

    db.flush()
    observe_vehicle_mileage(db, vehicle_id, entry_data.mileage)
    recompute_reminders(db, vehicle_id, [entry_data.type])

    db.commit()
    db.refresh(entry)
    return entry


@router.get("/{vehicle_id}/entries", response_model=List[MaintenanceEntryResponse])
def list_maintenance_entries(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db)
    return (
        db.query(MaintenanceEntry)
        .filter(MaintenanceEntry.vehicle_id == vehicle_id)
        .order_by(MaintenanceEntry.date.desc())
        .all()
    )


@router.get("/{vehicle_id}/entries/{entry_id}", response_model=MaintenanceEntryResponse)
def get_maintenance_entry(
    vehicle_id: int,
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db)
    entry = db.query(MaintenanceEntry).filter(
        MaintenanceEntry.id == entry_id, MaintenanceEntry.vehicle_id == vehicle_id
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Maintenance entry not found")
    return entry


@router.put("/{vehicle_id}/entries/{entry_id}", response_model=MaintenanceEntryResponse)
def update_maintenance_entry(
    vehicle_id: int,
    entry_id: int,
    entry_data: MaintenanceEntryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db, require_write=True)
    entry = db.query(MaintenanceEntry).filter(
        MaintenanceEntry.id == entry_id, MaintenanceEntry.vehicle_id == vehicle_id
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Maintenance entry not found")

    old_type = entry.type
    entry.date = entry_data.date
    entry.mileage = entry_data.mileage
    entry.type = entry_data.type
    entry.cost = entry_data.cost
    entry.service_provider = entry_data.service_provider
    entry.notes = entry_data.notes
    db.flush()
    observe_vehicle_mileage(db, vehicle_id, entry_data.mileage)
    recompute_reminders(db, vehicle_id, [old_type, entry_data.type])
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{vehicle_id}/entries/{entry_id}")
def delete_maintenance_entry(
    vehicle_id: int,
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db, require_write=True)
    entry = db.query(MaintenanceEntry).filter(
        MaintenanceEntry.id == entry_id, MaintenanceEntry.vehicle_id == vehicle_id
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Maintenance entry not found")
    service_type = entry.type
    db.delete(entry)
    db.flush()
    recompute_reminders(db, vehicle_id, [service_type])
    db.commit()
    return {"message": "Maintenance entry deleted"}


@router.post("/{vehicle_id}/reminders", response_model=MaintenanceReminderResponse)
def create_maintenance_reminder(
    vehicle_id: int,
    reminder_data: MaintenanceReminderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db, require_write=True)

    existing = db.query(MaintenanceReminder).filter(
        MaintenanceReminder.vehicle_id == vehicle_id,
        MaintenanceReminder.service_type == reminder_data.service_type,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Reminder for {reminder_data.service_type} already exists")

    reminder = MaintenanceReminder(
        vehicle_id=vehicle_id,
        service_type=reminder_data.service_type,
        interval_miles=reminder_data.interval_miles,
        interval_days=reminder_data.interval_days,
        target_mileage=reminder_data.target_mileage,
        reminder_miles=reminder_data.reminder_miles,
    )
    db.add(reminder)
    db.flush()
    recompute_reminders(db, vehicle_id, [reminder_data.service_type])
    db.commit()
    db.refresh(reminder)
    return reminder


@router.get("/{vehicle_id}/reminders", response_model=List[MaintenanceReminderResponse])
def list_maintenance_reminders(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db)
    reminders = db.query(MaintenanceReminder).filter(MaintenanceReminder.vehicle_id == vehicle_id).all()
    return reminders


@router.put("/{vehicle_id}/reminders/{reminder_id}", response_model=MaintenanceReminderResponse)
def update_maintenance_reminder(
    vehicle_id: int,
    reminder_id: int,
    reminder_data: MaintenanceReminderUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db, require_write=True)
    reminder = db.query(MaintenanceReminder).filter(
        MaintenanceReminder.id == reminder_id, MaintenanceReminder.vehicle_id == vehicle_id
    ).first()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")

    for field, value in reminder_data.model_dump(exclude_unset=True).items():
        setattr(reminder, field, value)
    db.flush()
    recompute_reminders(db, vehicle_id, [reminder.service_type])
    db.commit()
    db.refresh(reminder)
    return reminder


@router.post("/{vehicle_id}/reminders/{reminder_id}/complete", response_model=MaintenanceEntryResponse)
def complete_maintenance_reminder(
    vehicle_id: int,
    reminder_id: int,
    completion: MaintenanceCompletionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db, require_write=True)
    try:
        operation_id = str(UUID(completion.operation_id))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid operation ID") from exc
    payload_hash = hashlib.sha256(json.dumps(
        completion.model_dump(mode="json", exclude={"operation_id"}),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()).hexdigest()
    observe_vehicle_mileage(db, vehicle_id, completion.mileage)
    reminder = db.query(MaintenanceReminder).filter(
        MaintenanceReminder.id == reminder_id,
        MaintenanceReminder.vehicle_id == vehicle_id,
    ).with_for_update().first()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    previous = db.query(MaintenanceCompletionOperation).filter(
        MaintenanceCompletionOperation.user_id == current_user.id,
        MaintenanceCompletionOperation.operation_id == operation_id,
    ).first()
    if previous:
        if previous.vehicle_id != vehicle_id or previous.reminder_id != reminder_id or previous.payload_hash != payload_hash:
            raise HTTPException(status_code=409, detail="Idempotency operation conflict")
        return previous.maintenance_entry
    entry = MaintenanceEntry(
        vehicle_id=vehicle_id,
        date=completion.date,
        mileage=completion.mileage,
        type=reminder.service_type,
        cost=completion.cost,
        service_provider=completion.service_provider,
        notes=completion.notes,
    )
    db.add(entry)
    db.flush()
    recompute_reminders(db, vehicle_id, [reminder.service_type])
    db.add(MaintenanceCompletionOperation(
        user_id=current_user.id,
        operation_id=operation_id,
        vehicle_id=vehicle_id,
        reminder_id=reminder_id,
        payload_hash=payload_hash,
        maintenance_entry_id=entry.id,
    ))
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{vehicle_id}/reminders/{reminder_id}")
def delete_maintenance_reminder(
    vehicle_id: int,
    reminder_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db, require_write=True)
    reminder = db.query(MaintenanceReminder).filter(
        MaintenanceReminder.id == reminder_id, MaintenanceReminder.vehicle_id == vehicle_id
    ).first()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    db.delete(reminder)
    db.commit()
    return {"message": "Reminder deleted"}


@router.get("/{vehicle_id}/stats")
def get_maintenance_stats(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db)
    entries = db.query(MaintenanceEntry).filter(MaintenanceEntry.vehicle_id == vehicle_id).all()

    by_type: dict = {}
    for entry in entries:
        if entry.type not in by_type:
            by_type[entry.type] = {"count": 0, "total_cost": 0}
        by_type[entry.type]["count"] += 1
        by_type[entry.type]["total_cost"] += entry.cost

    return {
        "total_cost": sum(e.cost for e in entries),
        "entries_count": len(entries),
        "by_type": by_type,
    }
