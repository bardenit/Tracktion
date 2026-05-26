from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
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
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


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
    document_type: str,
    file: UploadFile = File(...),
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

    storage = get_storage()
    if isinstance(storage, LocalStorage):
        full_path = os.path.join(DATA_DIR, 'documents', doc.storage_path)
        if not os.path.exists(full_path):
            raise HTTPException(status_code=404, detail="File not found on disk")
        with open(full_path, 'rb') as f:
            content = f.read()
        media_type = 'application/octet-stream'
        if doc.filename:
            if doc.filename.endswith('.pdf'):
                media_type = 'application/pdf'
            elif doc.filename.lower().endswith(('.jpg', '.jpeg')):
                media_type = 'image/jpeg'
            elif doc.filename.lower().endswith('.png'):
                media_type = 'image/png'
        return StreamingResponse(
            io.BytesIO(content),
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{doc.filename}"'},
        )
    # For S3/WebDAV: return metadata (presigned URLs are a future enhancement)
    return {"filename": doc.filename, "storage_path": doc.storage_path, "type": doc.document_type}


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
