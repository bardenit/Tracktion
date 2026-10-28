"""One fuel station, one name.

The spellings pinned here are the real ones: a single Costco had arrived as
`Costco`, `Costco Gasoline`, `Costco Wholesale` and `COSTCO WHOLESALE`, and a
`Marathon ` with a trailing space read as a second Marathon.
"""

from datetime import date as date_type

from alembic import command
import pytest
from sqlalchemy import create_engine, text


def test_tidy_trims_collapses_and_drops_a_store_number():
    from app.services.station_names import tidy_station

    assert tidy_station("Marathon ") == "Marathon"
    assert tidy_station("  Speedway  ") == "Speedway"
    assert tidy_station("Costco  Gasoline") == "Costco Gasoline"
    assert tidy_station("Costco #4421") == "Costco"
    assert tidy_station("Costco # 4421") == "Costco"
    assert tidy_station("   ") is None
    assert tidy_station("") is None
    assert tidy_station(None) is None


def test_a_station_already_on_file_keeps_its_spelling():
    from app.services.station_names import canonical_station

    known = ["Costco", "Speedway"]
    assert canonical_station("Costco", known) == "Costco"
    assert canonical_station("costco", known) == "Costco"
    assert canonical_station("COSTCO", known) == "Costco"
    assert canonical_station("  speedway ", known) == "Speedway"


def test_a_longer_reading_collapses_onto_the_brand_root():
    from app.services.station_names import canonical_station

    known = ["Costco", "Marathon"]
    assert canonical_station("Costco Gasoline", known) == "Costco"
    assert canonical_station("COSTCO WHOLESALE", known) == "Costco"
    assert canonical_station("Costco Wholesale", known) == "Costco"


def test_the_root_has_to_land_on_a_word_boundary():
    from app.services.station_names import canonical_station

    # Shares six letters with Costco and is a different shop.
    assert canonical_station("Costcutter", ["Costco"]) == "Costcutter"
    assert canonical_station("Shelly's Garage", ["Shell"]) == "Shelly's Garage"


def test_an_unfamiliar_station_is_stored_as_given():
    from app.services.station_names import canonical_station

    assert canonical_station("Love's", ["Costco"]) == "Love's"
    assert canonical_station("BP", []) == "BP"
    assert canonical_station(None, ["Costco"]) is None


def test_collapsing_converges_when_both_spellings_are_on_file():
    from app.services.station_names import canonical_station

    # The root wins over an exact match, or the longer spelling would keep
    # itself alive for as long as one row still carried it.
    known = ["Costco Gasoline", "Costco"]
    assert canonical_station("Costco Gasoline", known) == "Costco"
    assert canonical_station(canonical_station("Costco Gasoline", known), known) == "Costco"


def test_the_shortest_root_wins_not_the_most_used():
    from app.services.station_names import canonical_station

    known = ["Costco Wholesale", "Costco"]
    assert canonical_station("Costco Wholesale Gasoline", known) == "Costco"


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
