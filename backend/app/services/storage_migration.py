import hashlib
import uuid

from sqlalchemy.orm import Session

from app.models import Document, StorageMigration, StorageMigrationObject, StorageProfile
from app.storage import get_storage, new_object_key


ACTIVE_STATES = {"pending", "running", "failed"}


def create_migration(db: Session, configuration: dict) -> StorageMigration:
    source = db.query(StorageProfile).filter_by(is_active=True).with_for_update().first()
    if source is None:
        from app.storage import get_active_profile
        source = get_active_profile(db)
    active = db.query(StorageMigration).filter(StorageMigration.state.in_(ACTIVE_STATES)).first()
    if active:
        raise ValueError("A storage migration is already active")
    candidate = StorageProfile(
        profile_uuid=str(uuid.uuid4()), backend_type=configuration.get("type", "local"),
        configuration=configuration, credential_version=1, is_active=False,
    )
    db.add(candidate)
    db.flush()
    migration = StorageMigration(source_profile_id=source.id, destination_profile_id=candidate.id,
                                 candidate_credential_version=candidate.credential_version, state="pending")
    db.add(migration)
    db.flush()
    source_storage = get_storage(source)
    for doc in db.query(Document).filter_by(storage_profile_id=source.id).order_by(Document.id).all():
        data = source_storage.load(doc.storage_path)
        digest = hashlib.sha256(data).hexdigest()
        doc.byte_length = len(data)
        doc.sha256 = digest
        db.add(StorageMigrationObject(
            migration_id=migration.id, document_id=doc.id, source_profile_id=source.id,
            destination_profile_id=candidate.id, source_key=doc.storage_path,
            destination_key=new_object_key(0, doc.vehicle_id), byte_length=len(data), sha256=digest,
            state="pending",
        ))
    db.commit()
    db.refresh(migration)
    return migration


def run_migration(db: Session, migration_id: int) -> StorageMigration:
    migration = db.get(StorageMigration, migration_id)
    if not migration or migration.state in {"complete", "cancelled"}:
        raise ValueError("Storage migration cannot be started")
    source = db.get(StorageProfile, migration.source_profile_id)
    candidate = db.get(StorageProfile, migration.destination_profile_id)
    source_storage = get_storage(source)
    candidate_storage = get_storage(candidate)
    inventoried = {row.document_id for row in db.query(StorageMigrationObject).filter_by(migration_id=migration.id)}
    for doc in db.query(Document).filter_by(storage_profile_id=source.id).order_by(Document.id):
        if doc.id in inventoried:
            continue
        data = source_storage.load(doc.storage_path)
        digest = hashlib.sha256(data).hexdigest()
        doc.byte_length, doc.sha256 = len(data), digest
        db.add(StorageMigrationObject(
            migration_id=migration.id, document_id=doc.id, source_profile_id=source.id,
            destination_profile_id=candidate.id, source_key=doc.storage_path,
            destination_key=new_object_key(0, doc.vehicle_id), byte_length=len(data), sha256=digest,
            state="pending",
        ))
    db.commit()
    migration.state = "running"
    db.commit()
    for item in db.query(StorageMigrationObject).filter_by(migration_id=migration.id).order_by(StorageMigrationObject.id):
        if not copy_and_verify(db, item.id, source_storage, candidate_storage):
            migration.state = "failed"
            db.commit()
            return migration
    if not cutover(db, migration.id):
        migration.state = "failed"
        db.commit()
    db.refresh(migration)
    return migration


def migration_status(db: Session, migration_id: int) -> dict:
    migration = db.get(StorageMigration, migration_id)
    if not migration:
        raise ValueError("Storage migration not found")
    rows = db.query(StorageMigrationObject).filter_by(migration_id=migration.id).all()
    counts = {state: sum(row.state == state for row in rows) for state in ("pending", "copied", "verified", "failed")}
    return {"id": migration.id, "state": migration.state, "total": len(rows), **counts}


def cancel_migration(db: Session, migration_id: int) -> StorageMigration:
    migration = db.get(StorageMigration, migration_id)
    if not migration or migration.state not in ACTIVE_STATES:
        raise ValueError("Storage migration cannot be cancelled")
    migration.state = "cancelled"
    db.commit()
    return migration


def copy_and_verify(db: Session, object_id: int, source, destination) -> bool:
    item = db.get(StorageMigrationObject, object_id)
    if item.state == "verified":
        return True
    try:
        if item.state in {"pending", "failed"}:
            data = source.load(item.source_key)
            if len(data) != item.byte_length or hashlib.sha256(data).hexdigest() != item.sha256:
                raise ValueError("source digest mismatch")
            destination.save(data, item.destination_key)
            item.state = "copied"
            item.error = None
            db.commit()
        copied = destination.load(item.destination_key)
        if len(copied) != item.byte_length or hashlib.sha256(copied).hexdigest() != item.sha256:
            raise ValueError("destination digest mismatch")
        item.state = "verified"
        db.commit()
        return True
    except Exception as exc:
        item.state = "failed"
        item.error = str(exc)[:1000]
        db.commit()
        return False


def cutover(db: Session, migration_id: int) -> bool:
    migration = db.get(StorageMigration, migration_id)
    candidate = db.get(StorageProfile, migration.destination_profile_id)
    source = db.query(StorageProfile).filter_by(id=migration.source_profile_id).with_for_update().first()
    if source is None or not source.is_active:
        return False
    referenced = db.query(Document).filter(Document.storage_profile_id == migration.source_profile_id).all()
    ledger = {row.document_id: row for row in db.query(StorageMigrationObject).filter_by(migration_id=migration.id).all()}
    if candidate.credential_version != migration.candidate_credential_version:
        return False
    if any(doc.id not in ledger or ledger[doc.id].state != "verified" for doc in referenced):
        return False
    for doc in referenced:
        doc.storage_profile_id = migration.destination_profile_id
        doc.storage_path = ledger[doc.id].destination_key
    db.query(StorageProfile).filter_by(is_active=True).update({"is_active": False})
    candidate.is_active = True
    migration.state = "complete"
    db.commit()
    return True
