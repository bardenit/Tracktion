import json

from alembic import command
from sqlalchemy import create_engine, inspect, text
import pytest


def test_fresh_sqlite_database_upgrades_to_head(db_url):
    from app.migrations import HEAD_REVISION, upgrade_database

    result = upgrade_database(db_url)
    engine = create_engine(db_url)

    assert result == HEAD_REVISION
    assert "partial_fillup" in {column["name"] for column in inspect(engine).get_columns("fuel_entries")}
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD_REVISION


def test_repeated_upgrade_is_clean(db_url):
    from app.migrations import HEAD_REVISION, upgrade_database

    assert upgrade_database(db_url) == HEAD_REVISION
    assert upgrade_database(db_url) == HEAD_REVISION


def test_unversioned_database_is_not_ready(db_url):
    from app.migrations import HEAD_REVISION, require_database_current

    engine = create_engine(db_url)
    with pytest.raises(RuntimeError, match=f"expected .*{HEAD_REVISION}"):
        require_database_current(engine)


def test_upgrade_restores_configured_s3_profile_and_legacy_primary_photos(db_url, tmp_path, monkeypatch):
    from app import data_config
    from app.migrations import HEAD_REVISION, alembic_config, upgrade_database

    command.upgrade(alembic_config(db_url), "0008_installation_state")
    engine = create_engine(db_url)
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO users (id, email, password_hash, is_admin) "
            "VALUES (1, 'owner@example.test', 'hash', true)"
        ))
        connection.execute(text(
            "INSERT INTO vehicles (id, user_id, make, model, year, primary_photo_id) "
            "VALUES (1, 1, 'Honda', 'Civic', 2020, NULL)"
        ))
        connection.execute(text(
            "INSERT INTO documents "
            "(id, vehicle_id, filename, storage_path, storage_profile_id, document_type) "
            "VALUES (4, 1, 'photo.png', 'user_1/vehicle_1/photo.png', "
            "(SELECT id FROM storage_profiles WHERE is_active = true), 'vehicle_photo')"
        ))

    storage_config = {
        "type": "s3",
        "endpoint": "https://s3.example.test",
        "bucket": "tracktion",
        "region": "us-east-1",
        "access_key": "access",
        "secret_key": "secret",
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"storage": storage_config}))
    monkeypatch.setattr(data_config, "CONFIG_FILE", config_file)

    assert upgrade_database(db_url) == HEAD_REVISION
    with engine.connect() as connection:
        profile = connection.execute(text(
            "SELECT id, backend_type, configuration FROM storage_profiles WHERE is_active = true"
        )).mappings().one()
        assert profile["backend_type"] == "s3"
        assert json.loads(profile["configuration"]) == storage_config
        assert connection.scalar(text("SELECT storage_profile_id FROM documents WHERE id = 4")) == profile["id"]
        assert connection.scalar(text("SELECT primary_photo_id FROM vehicles WHERE id = 1")) == 4
