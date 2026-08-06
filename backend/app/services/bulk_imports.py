import hashlib
import json
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import BulkImportOperation


def begin_bulk_import(db: Session, user_id: int, vehicle_id: int, resource: str, payload) -> tuple[str, str, BulkImportOperation | None]:
    try:
        operation_id = str(UUID(payload.operation_id))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid import operation ID") from exc
    encoded = payload.model_dump(mode="json", exclude={"operation_id"})
    payload_hash = hashlib.sha256(json.dumps(encoded, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    previous = db.query(BulkImportOperation).filter(
        BulkImportOperation.user_id == user_id,
        BulkImportOperation.operation_id == operation_id,
    ).first()
    if previous and (previous.vehicle_id != vehicle_id or previous.resource != resource or previous.payload_hash != payload_hash):
        raise HTTPException(status_code=409, detail="Import operation conflict")
    return operation_id, payload_hash, previous


def finish_bulk_import(db: Session, user_id: int, vehicle_id: int, resource: str, operation_id: str, payload_hash: str, count: int) -> None:
    db.add(BulkImportOperation(
        user_id=user_id, vehicle_id=vehicle_id, resource=resource,
        operation_id=operation_id, payload_hash=payload_hash, imported_count=count,
    ))
