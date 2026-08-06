from datetime import date, timedelta
from typing import Iterable

from sqlalchemy.orm import Session

from app.models import MaintenanceEntry, MaintenanceReminder, Vehicle


def recompute_reminders(db: Session, vehicle_id: int, service_types: Iterable[str]) -> None:
    names = sorted(set(service_types))
    if not names:
        return
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).with_for_update().one()
    reminders = (
        db.query(MaintenanceReminder)
        .filter(
            MaintenanceReminder.vehicle_id == vehicle_id,
            MaintenanceReminder.service_type.in_(names),
        )
        .order_by(MaintenanceReminder.service_type, MaintenanceReminder.id)
        .with_for_update()
        .all()
    )
    ordered_entries = (
        db.query(MaintenanceEntry)
        .filter(
            MaintenanceEntry.vehicle_id == vehicle_id,
            MaintenanceEntry.type.in_(names),
        )
        .order_by(
            MaintenanceEntry.type,
            MaintenanceEntry.date.desc(),
            MaintenanceEntry.mileage.desc(),
            MaintenanceEntry.id.desc(),
        )
        .all()
    )
    latest_by_type = {}
    for entry in ordered_entries:
        latest_by_type.setdefault(entry.type, entry)
    today = date.today()
    for reminder in reminders:
        latest = latest_by_type.get(reminder.service_type)
        reminder.last_performed_mileage = latest.mileage if latest else None
        reminder.last_performed_date = latest.date if latest else None
        reminder.next_due_mileage = (
            latest.mileage + reminder.interval_miles
            if latest and reminder.interval_miles is not None
            else reminder.target_mileage
        )
        reminder.next_due_date = (
            latest.date + timedelta(days=reminder.interval_days)
            if latest and reminder.interval_days is not None
            else None
        )
        reminder.is_overdue = bool(
            (reminder.next_due_mileage is not None and vehicle.current_mileage >= reminder.next_due_mileage)
            or (reminder.next_due_date is not None and today >= reminder.next_due_date)
        )
