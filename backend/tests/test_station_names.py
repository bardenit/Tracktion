"""One station, one name. One shop, one name.

The spellings pinned here are the real ones: a single Costco had arrived as
`Costco`, `Costco Gasoline`, `Costco Wholesale` and `COSTCO WHOLESALE`, and a
`Marathon ` with a trailing space read as a second Marathon. On the maintenance
side one dealer was `TodDWenzel` nine times by hand where the invoice its OCR
reads heads itself `Todd Wenzel GMC`, and one truck stop was `Loves` for a shop
that writes itself `Love's`.
"""

from datetime import date as date_type

from alembic import command
import pytest
from sqlalchemy import create_engine, text


def test_tidy_trims_collapses_and_drops_a_store_number():
    from app.services.station_names import tidy_name

    assert tidy_name("Marathon ") == "Marathon"
    assert tidy_name("  Speedway  ") == "Speedway"
    assert tidy_name("Costco  Gasoline") == "Costco Gasoline"
    assert tidy_name("Costco #4421") == "Costco"
    assert tidy_name("Costco # 4421") == "Costco"
    assert tidy_name("   ") is None
    assert tidy_name("") is None
    assert tidy_name(None) is None


def test_a_station_already_on_file_keeps_its_spelling():
    from app.services.station_names import canonical_name

    known = ["Costco", "Speedway"]
    assert canonical_name("Costco", known) == "Costco"
    assert canonical_name("costco", known) == "Costco"
    assert canonical_name("COSTCO", known) == "Costco"
    assert canonical_name("  speedway ", known) == "Speedway"


def test_a_longer_reading_collapses_onto_the_brand_root():
    from app.services.station_names import canonical_name

    known = ["Costco", "Marathon"]
    assert canonical_name("Costco Gasoline", known) == "Costco"
    assert canonical_name("COSTCO WHOLESALE", known) == "Costco"
    assert canonical_name("Costco Wholesale", known) == "Costco"


def test_the_root_has_to_land_on_a_word_boundary():
    from app.services.station_names import canonical_name

    # Shares six letters with Costco and is a different shop.
    assert canonical_name("Costcutter", ["Costco"]) == "Costcutter"
    assert canonical_name("Shelly's Garage", ["Shell"]) == "Shelly's Garage"


def test_an_unfamiliar_station_is_stored_as_given():
    from app.services.station_names import canonical_name

    assert canonical_name("Love's", ["Costco"]) == "Love's"
    assert canonical_name("BP", []) == "BP"
    assert canonical_name(None, ["Costco"]) is None


def test_collapsing_converges_when_both_spellings_are_on_file():
    from app.services.station_names import canonical_name

    # The root wins over an exact match, or the longer spelling would keep
    # itself alive for as long as one row still carried it.
    known = ["Costco Gasoline", "Costco"]
    assert canonical_name("Costco Gasoline", known) == "Costco"
    assert canonical_name(canonical_name("Costco Gasoline", known), known) == "Costco"


def test_the_shortest_root_wins_not_the_most_used():
    from app.services.station_names import canonical_name

    known = ["Costco Wholesale", "Costco"]
    assert canonical_name("Costco Wholesale Gasoline", known) == "Costco"


def test_known_names_come_back_most_used_first(db_session, seeded_objects):
    from app.models import FuelEntry
    from app.services.station_names import known_station_names

    _, _, vehicle = seeded_objects
    for index, location in enumerate(["Speedway", "Costco", "Costco", "Costco", "", None]):
        db_session.add(FuelEntry(
            vehicle_id=vehicle.id, date=date_type(2026, 1, index + 1),
            mileage=1_000 + index * 100, gallons=10, cost=30, location=location,
        ))
    db_session.commit()

    assert known_station_names(db_session, vehicle.user_id) == ["Costco", "Speedway"]


def test_another_fleet_names_do_not_leak_in(db_session, seeded_objects):
    from app.models import FuelEntry, Vehicle
    from app.services.station_names import known_station_names

    owner, collaborator, vehicle = seeded_objects
    other = Vehicle(user_id=collaborator.id, make="Ford", model="F150", year=2019)
    db_session.add(other)
    db_session.flush()
    db_session.add(FuelEntry(vehicle_id=other.id, date=date_type(2026, 1, 1), mileage=10, gallons=10, cost=30, location="Wawa"))
    db_session.add(FuelEntry(vehicle_id=vehicle.id, date=date_type(2026, 1, 1), mileage=10, gallons=10, cost=30, location="Costco"))
    db_session.commit()

    assert known_station_names(db_session, owner.id) == ["Costco"]
    assert known_station_names(db_session, collaborator.id) == ["Wawa"]


@pytest.mark.parametrize("typed,stored", [
    ("Costco Gasoline", "Costco"),
    ("COSTCO WHOLESALE", "Costco"),
    ("costco", "Costco"),
    ("Costco #118", "Costco"),
    ("Marathon ", "Marathon"),
    ("Meijer", "Meijer"),
])
def test_saving_a_fill_up_normalizes_the_station(app_client, seeded_objects, typed, stored):
    _, _, vehicle = seeded_objects
    first = app_client.post(f"/api/fuel/{vehicle.id}/entries", json={
        "date": "2026-01-01", "mileage": 1_000, "gallons": 10, "cost": 30, "location": "Costco",
    })
    assert first.status_code == 200, first.text

    second = app_client.post(f"/api/fuel/{vehicle.id}/entries", json={
        "date": "2026-01-02", "mileage": 1_300, "gallons": 10, "cost": 30, "location": typed,
    })
    assert second.status_code == 200, second.text
    assert second.json()["location"] == stored


def test_editing_a_fill_up_normalizes_the_station(app_client, seeded_objects):
    _, _, vehicle = seeded_objects
    created = app_client.post(f"/api/fuel/{vehicle.id}/entries", json={
        "date": "2026-01-01", "mileage": 1_000, "gallons": 10, "cost": 30, "location": "Costco",
    })
    entry_id = created.json()["id"]

    updated = app_client.put(f"/api/fuel/{vehicle.id}/entries/{entry_id}", json={
        "date": "2026-01-01", "mileage": 1_000, "gallons": 10, "cost": 30, "location": "COSTCO WHOLESALE",
    })
    assert updated.status_code == 200, updated.text
    assert updated.json()["location"] == "Costco"


def test_a_bulk_import_collapses_spellings_within_the_batch(app_client, seeded_objects):
    _, _, vehicle = seeded_objects
    response = app_client.post(f"/api/fuel/{vehicle.id}/entries/bulk", json={
        "operation_id": "6f1b7c9e-0d4a-4f2b-9c3e-2a7d5b8e1f04",
        "entries": [
            {"date": "2026-02-01", "mileage": 2_000, "gallons": 10, "cost": 30, "location": "Costco"},
            {"date": "2026-02-02", "mileage": 2_300, "gallons": 10, "cost": 30, "location": "Costco Gasoline"},
            {"date": "2026-02-03", "mileage": 2_600, "gallons": 10, "cost": 30, "location": "COSTCO WHOLESALE"},
        ],
    })
    assert response.status_code == 200, response.text

    listed = app_client.get(f"/api/fuel/{vehicle.id}/entries").json()
    assert {entry["location"] for entry in listed} == {"Costco"}


def test_migration_collapses_the_spellings_already_stored(db_url):
    from app.migrations import HEAD_REVISION, alembic_config, upgrade_database

    command.upgrade(alembic_config(db_url), "0010_maintenance_visits")
    engine = create_engine(db_url)
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO users (id, email, password_hash, is_admin) "
            "VALUES (1, 'owner@example.test', 'hash', true), (2, 'other@example.test', 'hash', false)"
        ))
        connection.execute(text(
            "INSERT INTO vehicles (id, user_id, make, model, year) "
            "VALUES (1, 1, 'Honda', 'Civic', 2020), (2, 2, 'Ford', 'F150', 2019)"
        ))
        spellings = [
            "Costco", "Costco", "Costco Gasoline", "COSTCO WHOLESALE",
            "Costco Wholesale", "Marathon", "Marathon ", "Costcutter", "   ",
        ]
        for index, location in enumerate(spellings):
            connection.execute(
                text("INSERT INTO fuel_entries (id, vehicle_id, date, mileage, gallons, cost, location) "
                     "VALUES (:id, 1, :date, :mileage, 10, 30, :location)"),
                {"id": index + 1, "date": f"2026-03-{index + 1:02d}", "mileage": 1_000 + index * 100,
                 "location": location},
            )
        # A second fleet keeps its own spelling: nothing crosses owners.
        connection.execute(text(
            "INSERT INTO fuel_entries (id, vehicle_id, date, mileage, gallons, cost, location) "
            "VALUES (99, 2, '2026-03-01', 500, 10, 30, 'COSTCO WHOLESALE')"
        ))

    assert upgrade_database(db_url) == HEAD_REVISION

    with engine.connect() as connection:
        stored = connection.execute(text(
            "SELECT location, count(*) FROM fuel_entries WHERE vehicle_id = 1 GROUP BY location"
        )).fetchall()
        assert dict(stored) == {"Costco": 5, "Marathon": 2, "Costcutter": 1, None: 1}
        other = connection.execute(text("SELECT location FROM fuel_entries WHERE vehicle_id = 2")).scalar()
        assert other == "COSTCO WHOLESALE"


def test_migration_is_safe_to_run_twice(db_url):
    from app.migrations import HEAD_REVISION, upgrade_database

    assert upgrade_database(db_url) == HEAD_REVISION
    assert upgrade_database(db_url) == HEAD_REVISION


# ── The same rules, applied to service shops ─────────────────────────────────

def test_punctuation_and_spacing_do_not_make_a_second_place():
    from app.services.station_names import canonical_name

    # Whichever spelling is on file is the one that survives. Without this,
    # fixing `Loves` to `Love's` would last until the next time it was typed.
    assert canonical_name("Loves", ["Love's"]) == "Love's"
    assert canonical_name("LOVES", ["Love's"]) == "Love's"
    assert canonical_name("Love's", ["Loves"]) == "Loves"
    assert canonical_name("TodDWenzel", ["Todd Wenzel"]) == "Todd Wenzel"
    assert canonical_name("todd  wenzel", ["Todd Wenzel"]) == "Todd Wenzel"


def test_a_longer_reading_of_a_shop_collapses_onto_the_shop():
    from app.services.station_names import canonical_name

    known = ["Todd Wenzel", "Al Serra"]
    assert canonical_name("Todd Wenzel GMC", known) == "Todd Wenzel"
    assert canonical_name("Al Serra Auto Plaza", known) == "Al Serra"
    # The word boundary still has to land: a different shop stays its own.
    assert canonical_name("Todds Garage", known) == "Todds Garage"


def test_known_shop_names_come_back_most_used_first(db_session, seeded_objects):
    from app.models import MaintenanceEntry
    from app.services.station_names import known_shop_names

    _, _, vehicle = seeded_objects
    for index, provider in enumerate(["Al Serra", "Todd Wenzel", "Todd Wenzel", "", None]):
        db_session.add(MaintenanceEntry(
            vehicle_id=vehicle.id, date=date_type(2026, 1, index + 1),
            mileage=1_000 + index * 100, type="Oil Change", cost=40, service_provider=provider,
        ))
    db_session.commit()

    assert known_shop_names(db_session, vehicle.user_id) == ["Todd Wenzel", "Al Serra"]


def test_another_fleets_shops_do_not_leak_in(db_session, seeded_objects):
    from app.models import MaintenanceEntry, Vehicle
    from app.services.station_names import known_shop_names

    owner, collaborator, vehicle = seeded_objects
    other = Vehicle(user_id=collaborator.id, make="Ford", model="F150", year=2019)
    db_session.add(other)
    db_session.flush()
    for owned_by, provider in [(other.id, "Jiffy Lube"), (vehicle.id, "Todd Wenzel")]:
        db_session.add(MaintenanceEntry(
            vehicle_id=owned_by, date=date_type(2026, 1, 1), mileage=10,
            type="Oil Change", cost=40, service_provider=provider,
        ))
    db_session.commit()

    assert known_shop_names(db_session, owner.id) == ["Todd Wenzel"]
    assert known_shop_names(db_session, collaborator.id) == ["Jiffy Lube"]


def _log_a_service(app_client, vehicle_id, provider, day=1, mileage=1_000):
    return app_client.post(f"/api/maintenance/{vehicle_id}/entries", json={
        "date": f"2026-01-{day:02d}", "mileage": mileage, "type": "Oil Change",
        "cost": 40, "service_provider": provider,
    })


@pytest.mark.parametrize("typed,stored", [
    ("Todd Wenzel GMC", "Todd Wenzel"),
    ("TODD WENZEL", "Todd Wenzel"),
    ("TodDWenzel", "Todd Wenzel"),
    ("Todd Wenzel #2", "Todd Wenzel"),
    ("todd wenzel ", "Todd Wenzel"),
    ("Jiffy Lube", "Jiffy Lube"),
])
def test_logging_a_service_normalizes_the_shop(app_client, seeded_objects, typed, stored):
    _, _, vehicle = seeded_objects
    assert _log_a_service(app_client, vehicle.id, "Todd Wenzel").status_code == 200

    logged = _log_a_service(app_client, vehicle.id, typed, day=2, mileage=6_000)
    assert logged.status_code == 200, logged.text
    assert logged.json()["service_provider"] == stored


def test_editing_a_service_normalizes_the_shop(app_client, seeded_objects):
    _, _, vehicle = seeded_objects
    created = _log_a_service(app_client, vehicle.id, "Todd Wenzel")
    entry_id = created.json()["id"]

    updated = app_client.put(f"/api/maintenance/{vehicle.id}/entries/{entry_id}", json={
        "date": "2026-01-01", "mileage": 1_000, "type": "Oil Change", "cost": 40,
        "service_provider": "TODD WENZEL GMC",
    })
    assert updated.status_code == 200, updated.text
    assert updated.json()["service_provider"] == "Todd Wenzel"


def test_a_visit_normalizes_the_shop_once_for_every_service(app_client, seeded_objects):
    from uuid import uuid4

    _, _, vehicle = seeded_objects
    assert _log_a_service(app_client, vehicle.id, "Todd Wenzel").status_code == 200

    visit = app_client.post(f"/api/maintenance/{vehicle.id}/visits", json={
        "operation_id": str(uuid4()), "date": "2026-02-01", "mileage": 6_000,
        "service_provider": "Todd Wenzel GMC",
        "services": [{"type": "Tire Rotation", "cost": 29.95}, {"type": "Cabin Air Filter", "cost": 79.95}],
    })
    assert visit.status_code == 200, visit.text
    assert {entry["service_provider"] for entry in visit.json()["entries"]} == {"Todd Wenzel"}


def test_completing_a_reminder_normalizes_the_shop(app_client, seeded_objects):
    from uuid import uuid4

    _, _, vehicle = seeded_objects
    assert _log_a_service(app_client, vehicle.id, "Todd Wenzel").status_code == 200
    reminder = app_client.post(f"/api/maintenance/{vehicle.id}/reminders", json={
        "service_type": "Tire Rotation", "interval_miles": 5_000,
    })
    assert reminder.status_code == 200, reminder.text

    completed = app_client.post(
        f"/api/maintenance/{vehicle.id}/reminders/{reminder.json()['id']}/complete",
        json={"operation_id": str(uuid4()), "date": "2026-02-01", "mileage": 6_000,
              "cost": 29.95, "service_provider": "TodDWenzel"},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["service_provider"] == "Todd Wenzel"


def test_a_maintenance_bulk_import_collapses_spellings_within_the_batch(app_client, seeded_objects):
    from uuid import uuid4

    _, _, vehicle = seeded_objects
    response = app_client.post(f"/api/maintenance/{vehicle.id}/entries/bulk", json={
        "operation_id": str(uuid4()),
        "entries": [
            {"date": "2026-03-01", "mileage": 2_000, "type": "Oil Change", "cost": 40,
             "service_provider": "Todd Wenzel"},
            {"date": "2026-03-02", "mileage": 2_300, "type": "Tire Rotation", "cost": 30,
             "service_provider": "Todd Wenzel GMC"},
            {"date": "2026-03-03", "mileage": 2_600, "type": "Brake Fluid", "cost": 90,
             "service_provider": "TODD WENZEL"},
        ],
    })
    assert response.status_code == 200, response.text

    listed = app_client.get(f"/api/maintenance/{vehicle.id}/entries").json()
    assert {entry["service_provider"] for entry in listed} == {"Todd Wenzel"}


def test_migration_fixes_the_names_no_rule_can_reach(db_url):
    from app.migrations import HEAD_REVISION, alembic_config, upgrade_database

    command.upgrade(alembic_config(db_url), "0011_normalize_station_names")
    engine = create_engine(db_url)
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO users (id, email, password_hash, is_admin) "
            "VALUES (1, 'owner@example.test', 'hash', true), (2, 'other@example.test', 'hash', false)"
        ))
        connection.execute(text(
            "INSERT INTO vehicles (id, user_id, make, model, year) "
            "VALUES (1, 1, 'Honda', 'Civic', 2020), (2, 2, 'Ford', 'F150', 2019)"
        ))
        # Nine hand-typed visits to one dealer, the invoice OCR's reading of the
        # same dealer, a lower-cased second shop, and a blank.
        providers = ["TodDWenzel"] * 3 + ["Todd Wenzel GMC", "Al serra", "Jiffy Lube", "  "]
        for index, provider in enumerate(providers):
            connection.execute(
                text("INSERT INTO maintenance_entries (id, vehicle_id, date, mileage, type, cost, service_provider) "
                     "VALUES (:id, 1, :date, :mileage, 'Oil Change', 40, :provider)"),
                {"id": index + 1, "date": f"2026-04-{index + 1:02d}",
                 "mileage": 1_000 + index * 100, "provider": provider},
            )
        # A misspelling is a misspelling in anyone's fleet, so the fixes are not
        # scoped to an owner the way the collapsing is.
        connection.execute(text(
            "INSERT INTO maintenance_entries (id, vehicle_id, date, mileage, type, cost, service_provider) "
            "VALUES (99, 2, '2026-04-01', 500, 'Oil Change', 40, 'TodDWenzel')"
        ))
        connection.execute(text(
            "INSERT INTO fuel_entries (id, vehicle_id, date, mileage, gallons, cost, location) "
            "VALUES (1, 1, '2026-04-01', 1000, 10, 30, 'Loves'), "
            "(2, 1, '2026-04-02', 1100, 10, 30, 'Costco')"
        ))

    assert upgrade_database(db_url) == HEAD_REVISION

    with engine.connect() as connection:
        shops = connection.execute(text(
            "SELECT service_provider, count(*) FROM maintenance_entries WHERE vehicle_id = 1 "
            "GROUP BY service_provider"
        )).fetchall()
        assert dict(shops) == {"Todd Wenzel": 4, "Al Serra": 1, "Jiffy Lube": 1, None: 1}
        assert connection.execute(text(
            "SELECT service_provider FROM maintenance_entries WHERE vehicle_id = 2"
        )).scalar() == "Todd Wenzel"
        locations = connection.execute(text(
            "SELECT location, count(*) FROM fuel_entries GROUP BY location"
        )).fetchall()
        assert dict(locations) == {"Love's": 1, "Costco": 1}
