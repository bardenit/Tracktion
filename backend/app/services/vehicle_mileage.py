from datetime import date

from sqlalchemy.orm import Session

from app.models import MaintenanceReminder, Vehicle


def observe_vehicle_mileage(db: Session, vehicle_id: int, mileage: float) -> Vehicle:
    """Record an absolute odometer observation without ever moving it backwards."""
    vehicle = (
        db.query(Vehicle)
        .filter(Vehicle.id == vehicle_id)
        .with_for_update()
        .one()
    )
    vehicle.current_mileage = max(float(vehicle.current_mileage or 0), float(mileage))
    for reminder in (
        db.query(MaintenanceReminder)
        .filter(MaintenanceReminder.vehicle_id == vehicle_id)
        .order_by(MaintenanceReminder.id)
        .with_for_update()
        .all()
    ):
        reminder.is_overdue = bool(
            (reminder.next_due_mileage is not None and vehicle.current_mileage >= reminder.next_due_mileage)
            or (reminder.next_due_date is not None and date.today() >= reminder.next_due_date)
        )
    return vehicle
