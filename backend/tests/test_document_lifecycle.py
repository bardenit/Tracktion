import pytest


def test_object_keys_are_immutable_uuid_names():
    from app.storage import new_object_key

    first = new_object_key(1, 2)
    second = new_object_key(1, 2)
    assert first != second
    assert first.startswith("tracktion/objects/")
    assert first.count("/") == 2


def test_content_detection_ignores_spoofed_header():
    from app.routes.documents import detect_content_type

    with pytest.raises(ValueError):
        detect_content_type(b"not a pdf", "application/pdf")
    assert detect_content_type(b"%PDF-1.7\n", "application/pdf") == "application/pdf"


def test_filename_removes_header_and_path_characters():
    from app.routes.documents import _safe_filename

    assert _safe_filename("../evil\r\nX-Bad: yes.pdf") == "evilX-Bad_yes.pdf"


def test_cleanup_rechecks_live_references(db_session):
    from app.models import Document, StorageCleanup
    from app.services.storage_cleanup import claim_cleanup

    cleanup = StorageCleanup(storage_profile_id=1, object_key="tracktion/objects/shared", state="pending")
    db_session.add(cleanup)
    db_session.add(Document(vehicle_id=1, filename="x", storage_path=cleanup.object_key,
                            storage_profile_id=1, document_type="other"))
    db_session.commit()
    assert claim_cleanup(db_session, cleanup.id) is None
    assert cleanup.state == "cancelled"


def test_cleanup_uses_owning_profile_backend(db_session, monkeypatch):
    from app.models import StorageCleanup, StorageProfile
    from app.services.storage_cleanup import run_cleanup

    profile = StorageProfile(profile_uuid="profile", backend_type="local", configuration={}, is_active=False)
    db_session.add(profile)
    db_session.flush()
    cleanup = StorageCleanup(storage_profile_id=profile.id, object_key="old/object", state="pending")
    db_session.add(cleanup)
    db_session.commit()
    deleted = []
    backend = type("Backend", (), {"delete": lambda self, key: deleted.append(key)})()
    monkeypatch.setattr("app.storage.get_storage_for_profile", lambda db, profile_id: backend)

    assert run_cleanup(db_session, cleanup.id) is True
    assert deleted == ["old/object"]


def test_photo_successor_is_oldest_then_lowest_id(db_session, seeded_objects):
    from datetime import datetime
    from app.models import Document
    from app.routes.documents import _photo_successor

    _, _, vehicle = seeded_objects
    photos = [Document(vehicle_id=vehicle.id, filename=str(i), storage_path=str(i),
                       document_type="vehicle_photo", uploaded_at=datetime(2024, 1, 1)) for i in range(3)]
    db_session.add_all(photos)
    db_session.commit()
    assert _photo_successor(db_session, vehicle.id, photos[0].id).id == photos[1].id
