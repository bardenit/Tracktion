from datetime import timedelta, date as date_type
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import User, MaintenanceEntry, MaintenanceReminder
from app.schemas import (
    MaintenanceEntryCreate,
    MaintenanceEntryResponse,
    MaintenanceReminderCreate,
    MaintenanceReminderUpdate,
    MaintenanceReminderResponse,
)
from app.auth import get_current_user
from app.deps import check_vehicle_access

router = APIRouter()


@router.post("/{vehicle_id}/entries", response_model=MaintenanceEntryResponse)
def create_maintenance_entry(
    vehicle_id: int,
    entry_data: MaintenanceEntryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vehicle = check_vehicle_access(vehicle_id, current_user.id, db, require_write=True)

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

    vehicle.current_mileage = max(vehicle.current_mileage, entry_data.mileage)

    reminder = (
        db.query(MaintenanceReminder)
        .filter(MaintenanceReminder.vehicle_id == vehicle_id, MaintenanceReminder.service_type == entry_data.type)
        .first()
    )
    if reminder:
        reminder.last_performed_mileage = entry_data.mileage
        reminder.last_performed_date = entry_data.date
        reminder.is_overdue = False
        if reminder.interval_miles:
            reminder.next_due_mileage = entry_data.mileage + reminder.interval_miles
        if reminder.interval_days:
            reminder.next_due_date = entry_data.date + timedelta(days=reminder.interval_days)

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

    entry.date = entry_data.date
    entry.mileage = entry_data.mileage
    entry.type = entry_data.type
    entry.cost = entry_data.cost
    entry.service_provider = entry_data.service_provider
    entry.notes = entry_data.notes

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
    db.delete(entry)
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

    last_mileage = None
    last_date = None
    next_due_mileage = reminder_data.target_mileage
    next_due_date = None

    if reminder_data.interval_miles or reminder_data.interval_days:
        last_entry = (
            db.query(MaintenanceEntry)
            .filter(MaintenanceEntry.vehicle_id == vehicle_id, MaintenanceEntry.type == reminder_data.service_type)
            .order_by(MaintenanceEntry.mileage.desc())
            .first()
        )
        if last_entry:
            last_mileage = last_entry.mileage
            last_date = last_entry.date
            if reminder_data.interval_miles:
                next_due_mileage = last_entry.mileage + reminder_data.interval_miles
            if reminder_data.interval_days:
                next_due_date = last_entry.date + timedelta(days=reminder_data.interval_days)

    reminder = MaintenanceReminder(
        vehicle_id=vehicle_id,
        service_type=reminder_data.service_type,
        interval_miles=reminder_data.interval_miles,
        interval_days=reminder_data.interval_days,
        target_mileage=reminder_data.target_mileage,
        reminder_miles=reminder_data.reminder_miles,
        last_performed_mileage=last_mileage,
        last_performed_date=last_date,
        next_due_mileage=next_due_mileage,
        next_due_date=next_due_date,
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


@router.get("/{vehicle_id}/reminders", response_model=List[MaintenanceReminderResponse])
def list_maintenance_reminders(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vehicle = check_vehicle_access(vehicle_id, current_user.id, db)
    reminders = db.query(MaintenanceReminder).filter(MaintenanceReminder.vehicle_id == vehicle_id).all()

    today = date_type.today()
    changed = False
    for r in reminders:
        overdue = (
            (r.next_due_mileage and vehicle.current_mileage >= r.next_due_mileage)
            or (r.next_due_date and today >= r.next_due_date)
            or (r.target_mileage and vehicle.current_mileage >= r.target_mileage)
        )
        if r.is_overdue != overdue:
            r.is_overdue = overdue
            changed = True
    if changed:
        db.commit()

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

    db.commit()
    db.refresh(reminder)
    return reminder


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
