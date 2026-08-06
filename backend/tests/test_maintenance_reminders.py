from datetime import date

from app.models import MaintenanceEntry, MaintenanceReminder
from app.services.maintenance_reminders import recompute_reminders


def test_recompute_uses_deterministic_latest_and_falls_back(db_session, seeded_objects):
    _, _, vehicle = seeded_objects
    reminder = MaintenanceReminder(vehicle_id=vehicle.id, service_type="Oil", interval_miles=5_000, interval_days=180)
    older = MaintenanceEntry(vehicle_id=vehicle.id, date=date(2026, 1, 1), mileage=10_000, type="Oil", cost=1)
    latest = MaintenanceEntry(vehicle_id=vehicle.id, date=date(2026, 2, 1), mileage=12_000, type="Oil", cost=1)
    db_session.add_all([reminder, older, latest])
    db_session.flush()

    recompute_reminders(db_session, vehicle.id, ["Oil"])
    assert reminder.last_performed_mileage == 12_000
    assert reminder.next_due_mileage == 17_000

    db_session.delete(latest)
    db_session.flush()
    recompute_reminders(db_session, vehicle.id, ["Oil"])
    assert reminder.last_performed_mileage == 10_000
    assert reminder.next_due_mileage == 15_000

    db_session.delete(older)
    db_session.flush()
    recompute_reminders(db_session, vehicle.id, ["Oil"])
    assert reminder.last_performed_mileage is None
    assert reminder.next_due_mileage is None


def test_target_reminder_does_not_invent_history(db_session, seeded_objects):
    _, _, vehicle = seeded_objects
    reminder = MaintenanceReminder(vehicle_id=vehicle.id, service_type="Tires", target_mileage=20_000)
    db_session.add(reminder)
    db_session.flush()
    recompute_reminders(db_session, vehicle.id, ["Tires"])
    assert reminder.last_performed_mileage is None
    assert reminder.next_due_mileage == 20_000

