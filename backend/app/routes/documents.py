from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List
import io
import os
from datetime import datetime
from app.database import get_db
from app.models import User, Vehicle, Document, VehicleCollaborator
from app.schemas import DocumentResponse
from app.auth import get_current_user
from app.storage import get_storage, LocalStorage
from app.data_config import DATA_DIR

router = APIRouter()

ALLOWED_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


def _media_type(filename: str) -> str:
    name = (filename or '').lower()
    if name.endswith(('.jpg', '.jpeg')):
        return 'image/jpeg'
    if name.endswith('.png'):
        return 'image/png'
    if name.endswith('.webp'):
        return 'image/webp'
    if name.endswith('.gif'):
        return 'image/gif'
    if name.endswith('.pdf'):
        return 'application/pdf'
    return 'application/octet-stream'


def _check_vehicle_access(vehicle_id: int, user_id: int, db: Session) -> Vehicle:
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    is_owner = vehicle.user_id == user_id
    is_collaborator = (
        db.query(VehicleCollaborator)
        .filter(VehicleCollaborator.vehicle_id == vehicle_id, VehicleCollaborator.user_id == user_id)
        .first() is not None
    )
    if not (is_owner or is_collaborator):
        raise HTTPException(status_code=403, detail="Access denied")
    return vehicle


@router.post("/{vehicle_id}/documents", response_model=DocumentResponse)
async def upload_document(
    vehicle_id: int,
    file: UploadFile = File(...),
    document_type: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _check_vehicle_access(vehicle_id, current_user.id, db)

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="File type not allowed. Allowed: PDF, Images, Word docs")

    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 20MB")

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_name = (file.filename or 'file').replace(" ", "_")
    relative_path = f"user_{current_user.id}/vehicle_{vehicle_id}/{timestamp}_{safe_name}"

    get_storage().save(data, relative_path, file.content_type or 'application/octet-stream')

    doc = Document(
        vehicle_id=vehicle_id,
        filename=file.filename,
        storage_path=relative_path,
        document_type=document_type,
        ocr_text=None,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.get("/{vehicle_id}/documents", response_model=List[DocumentResponse])
def list_documents(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _check_vehicle_access(vehicle_id, current_user.id, db)
    return (
        db.query(Document)
        .filter(Document.vehicle_id == vehicle_id)
        .order_by(Document.uploaded_at.desc())
        .all()
    )


@router.get("/{vehicle_id}/documents/{document_id}/download")
def download_document(
    vehicle_id: int,
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _check_vehicle_access(vehicle_id, current_user.id, db)
    doc = db.query(Document).filter(Document.id == document_id, Document.vehicle_id == vehicle_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        content = get_storage().load(doc.storage_path)
    except Exception:
        raise HTTPException(status_code=404, detail="File not found in storage")

    media_type = _media_type(doc.filename or '')
    disposition = 'inline' if media_type.startswith('image/') else 'attachment'
    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f'{disposition}; filename="{doc.filename}"'},
    )


@router.delete("/{vehicle_id}/documents/{document_id}")
def delete_document(
    vehicle_id: int,
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _check_vehicle_access(vehicle_id, current_user.id, db)
    doc = db.query(Document).filter(Document.id == document_id, Document.vehicle_id == vehicle_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    get_storage().delete(doc.storage_path)
    db.delete(doc)
    db.commit()
    return {"message": "Document deleted"}


# ── Vehicle photo endpoints ───────────────────────────────────────────────────

@router.post("/{vehicle_id}/photo")
async def upload_vehicle_photo(
    vehicle_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _check_vehicle_access(vehicle_id, current_user.id, db)

    if file.content_type not in IMAGE_TYPES and not (file.filename or '').lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif')):
        raise HTTPException(status_code=400, detail="Image files only (JPEG, PNG, WebP)")

    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 20 MB)")

    # Replace any existing photo
    existing = (
        db.query(Document)
        .filter(Document.vehicle_id == vehicle_id, Document.document_type == 'vehicle_photo')
        .first()
    )
    if existing:
        try:
            get_storage().delete(existing.storage_path)
        except Exception:
            pass
        db.delete(existing)
        db.flush()

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_name = (file.filename or 'photo').replace(" ", "_")
    relative_path = f"user_{current_user.id}/vehicle_{vehicle_id}/photo_{timestamp}_{safe_name}"
    get_storage().save(data, relative_path, file.content_type or 'image/jpeg')

    doc = Document(
        vehicle_id=vehicle_id,
        filename=file.filename,
        storage_path=relative_path,
        document_type='vehicle_photo',
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return {"id": doc.id, "filename": doc.filename}


@router.get("/{vehicle_id}/photo")
def get_vehicle_photo(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _check_vehicle_access(vehicle_id, current_user.id, db)
    doc = (
        db.query(Document)
        .filter(Document.vehicle_id == vehicle_id, Document.document_type == 'vehicle_photo')
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="No photo")
    try:
        content = get_storage().load(doc.storage_path)
    except Exception:
        raise HTTPException(status_code=404, detail="Photo not found in storage")
    media_type = _media_type(doc.filename or '')
    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{doc.filename}"'},
    )


@router.delete("/{vehicle_id}/photo")
def delete_vehicle_photo(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _check_vehicle_access(vehicle_id, current_user.id, db)
    doc = (
        db.query(Document)
        .filter(Document.vehicle_id == vehicle_id, Document.document_type == 'vehicle_photo')
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="No photo")
    try:
        get_storage().delete(doc.storage_path)
    except Exception:
        pass
    db.delete(doc)
    db.commit()
    return {"message": "Photo deleted"}
