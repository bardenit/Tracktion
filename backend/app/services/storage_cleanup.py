from sqlalchemy.orm import Session

from app.models import Document, StorageCleanup


def schedule_cleanup(db: Session, profile_id: int, object_key: str) -> StorageCleanup:
    existing = db.query(StorageCleanup).filter_by(storage_profile_id=profile_id, object_key=object_key).first()
    if existing:
        return existing
    cleanup = StorageCleanup(storage_profile_id=profile_id, object_key=object_key, state="pending")
    db.add(cleanup)
    return cleanup


def claim_cleanup(db: Session, cleanup_id: int) -> StorageCleanup | None:
    cleanup = db.get(StorageCleanup, cleanup_id)
    if not cleanup or cleanup.state not in {"pending", "failed"}:
        return None
    referenced = db.query(Document.id).filter_by(
        storage_profile_id=cleanup.storage_profile_id, storage_path=cleanup.object_key
    ).first()
    if referenced:
        cleanup.state = "cancelled"
        db.commit()
        return None
    cleanup.state = "claimed"
    cleanup.attempts += 1
    db.commit()
    return cleanup


def run_cleanup(db: Session, cleanup_id: int, storage=None) -> bool:
    cleanup = claim_cleanup(db, cleanup_id)
    if cleanup is None:
        return False
    try:
        if storage is None:
            from app.storage import get_storage_for_profile
            storage = get_storage_for_profile(db, cleanup.storage_profile_id)
        storage.delete(cleanup.object_key)
        cleanup.state = "complete"
        cleanup.last_error = None
    except Exception as exc:
        cleanup.state = "failed"
        cleanup.last_error = str(exc)[:1000]
    db.commit()
    return cleanup.state == "complete"
