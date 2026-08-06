import hashlib


class MemoryStorage:
    def __init__(self, objects=None):
        self.objects = dict(objects or {})

    def save(self, data, path, content_type="application/octet-stream"):
        self.objects[path] = data
        return path

    def load(self, path):
        return self.objects[path]

    def delete(self, path):
        self.objects.pop(path, None)


def test_copy_verify_is_resumable_and_digest_checked(db_session):
    from app.models import StorageMigrationObject
    from app.services.storage_migration import copy_and_verify

    payload = b"durable"
    item = StorageMigrationObject(migration_id=1, document_id=1, source_profile_id=1,
        destination_profile_id=2, source_key="old", destination_key="new",
        byte_length=len(payload), sha256=hashlib.sha256(payload).hexdigest(), state="pending")
    db_session.add(item)
    db_session.commit()
    source, destination = MemoryStorage({"old": payload}), MemoryStorage()
    copy_and_verify(db_session, item.id, source, destination)
    copy_and_verify(db_session, item.id, source, destination)
    assert item.state == "verified"
    assert destination.objects == {"new": payload}
    assert source.objects == {"old": payload}


def test_equal_length_corruption_never_verifies(db_session):
    from app.models import StorageMigrationObject
    from app.services.storage_migration import copy_and_verify

    item = StorageMigrationObject(migration_id=1, document_id=1, source_profile_id=1,
        destination_profile_id=2, source_key="old", destination_key="new",
        byte_length=4, sha256=hashlib.sha256(b"good").hexdigest(), state="copied")
    db_session.add(item)
    db_session.commit()
    source, destination = MemoryStorage({"old": b"good"}), MemoryStorage({"new": b"evil"})
    assert copy_and_verify(db_session, item.id, source, destination) is False
    assert item.state == "failed"


def test_profile_configuration_constructs_its_original_backend(monkeypatch):
    from app.models import StorageProfile
    from app import storage

    captured = {}
    monkeypatch.setattr(storage, "S3Storage", lambda cfg: captured.update(cfg) or "s3")
    profile = StorageProfile(backend_type="s3", configuration={"bucket": "archive"})
    assert storage.get_storage(profile) == "s3"
    assert captured == {"bucket": "archive", "type": "s3"}
