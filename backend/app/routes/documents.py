import io
import os
import re
import hashlib
from urllib.parse import quote
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import User, Vehicle, Document, MaintenanceEntry
from app.schemas import DocumentResponse, VehiclePhotoResponse
from app.auth import get_current_user
from app.deps import check_vehicle_access
from app.storage import get_storage, get_storage_for_profile, get_active_profile, new_object_key
from app.services.storage_cleanup import schedule_cleanup

router = APIRouter()

VALID_DOC_TYPES = {"registration", "insurance", "receipt", "service", "warranty", "other"}

IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


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


def _safe_filename(filename: str | None, fallback: str = 'file') -> str:
    name = os.path.basename((filename or fallback).replace("\\", "/"))
    name = re.sub(r"[\x00-\x1f\x7f:]", "", name).replace(" ", "_")
    return name[:255] or fallback


def detect_content_type(data: bytes) -> str:
    signatures = ((b"%PDF-", "application/pdf"), (b"\xff\xd8\xff", "image/jpeg"),
                  (b"\x89PNG\r\n\x1a\n", "image/png"), (b"RIFF", "image/webp"),
                  (b"PK\x03\x04", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
                  (b"\xd0\xcf\x11\xe0", "application/msword"))
    for signature, media_type in signatures:
        if data.startswith(signature):
            if media_type == "image/webp" and data[8:12] != b"WEBP":
                break
            return media_type
    if len(data) >= 12 and data[4:12] in {b"ftypheic", b"ftypheix", b"ftyphevc", b"ftyphevx", b"ftypmif1"}:
        return "image/heic"
    raise ValueError("File content does not match a supported type")


async def _read_limited(file: UploadFile) -> bytes:
    chunks, size = [], 0
    while chunk := await file.read(64 * 1024):
        size += len(chunk)
        if size > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File too large. Maximum size is 20MB")
        chunks.append(chunk)
    return b"".join(chunks)


def _photo_successor(db: Session, vehicle_id: int, excluding_id: int) -> Document | None:
    return (
        db.query(Document)
        .filter(Document.vehicle_id == vehicle_id, Document.document_type == "vehicle_photo", Document.id != excluding_id)
        .order_by(Document.uploaded_at.asc(), Document.id.asc())
        .first()
    )


@router.post("/{vehicle_id}/documents", response_model=DocumentResponse)
async def upload_document(
    vehicle_id: int,
    file: UploadFile = File(...),
    document_type: str = Form(...),
    maintenance_entry_id: int | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db, require_write=True)

    if document_type not in VALID_DOC_TYPES:
        raise HTTPException(status_code=400, detail="Invalid document type")

    if maintenance_entry_id is not None and not db.query(MaintenanceEntry.id).filter_by(
        id=maintenance_entry_id, vehicle_id=vehicle_id
    ).first():
        raise HTTPException(status_code=400, detail="Maintenance entry does not belong to this vehicle")
    data = await _read_limited(file)
    try:
        content_type = detect_content_type(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    safe_name = _safe_filename(file.filename)
    relative_path = new_object_key(current_user.id, vehicle_id)
    profile = get_active_profile(db)
    storage = get_storage(profile)
    storage.save(data, relative_path, content_type)

    doc = Document(
        vehicle_id=vehicle_id,
        maintenance_entry_id=maintenance_entry_id,
        filename=safe_name,
        storage_path=relative_path,
        storage_profile_id=profile.id,
        content_type=content_type,
        byte_length=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        document_type=document_type,
        ocr_text=None,
    )
    db.add(doc)
    try:
        db.commit()
    except Exception:
        db.rollback()
        try:
            storage.delete(relative_path)
        except Exception:
            cleanup = schedule_cleanup(db, profile.id, relative_path)
            db.commit()
        raise
    db.refresh(doc)
    return doc


@router.get("/{vehicle_id}/documents", response_model=List[DocumentResponse])
def list_documents(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db)
    return (
        db.query(Document)
        .filter(Document.vehicle_id == vehicle_id, Document.document_type != "vehicle_photo")
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
    check_vehicle_access(vehicle_id, current_user.id, db)
    doc = db.query(Document).filter(Document.id == document_id, Document.vehicle_id == vehicle_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        content = get_storage_for_profile(db, doc.storage_profile_id).load(doc.storage_path)
    except Exception:
        raise HTTPException(status_code=404, detail="File not found in storage")

    media_type = doc.content_type or _media_type(doc.filename or '')
    disposition = 'inline' if media_type.startswith('image/') else 'attachment'
    encoded_name = quote(doc.filename or 'file', safe='')
    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f"{disposition}; filename*=UTF-8''{encoded_name}",
                 "X-Content-Type-Options": "nosniff"},
    )


@router.delete("/{vehicle_id}/documents/{document_id}")
def delete_document(
    vehicle_id: int,
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db, require_write=True)
    doc = db.query(Document).filter(Document.id == document_id, Document.vehicle_id == vehicle_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    profile_id, object_key = doc.storage_profile_id, doc.storage_path
    db.delete(doc)
    if profile_id:
        cleanup = schedule_cleanup(db, profile_id, object_key)
    db.commit()
    if profile_id:
        from app.services.storage_cleanup import run_cleanup
        run_cleanup(db, cleanup.id)
    return {"message": "Document deleted"}


# ── Vehicle photo endpoints ───────────────────────────────────────────────────

@router.post("/{vehicle_id}/photo")
async def upload_vehicle_photo(
    vehicle_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db, require_write=True)

    if file.content_type not in IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Image files only (JPEG, PNG, WebP)")

    data = await _read_limited(file)
    try:
        content_type = detect_content_type(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if content_type not in IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Image files only (JPEG, PNG, WebP, HEIC)")
    safe_name = _safe_filename(file.filename, 'photo')
    relative_path = new_object_key(current_user.id, vehicle_id)
    profile = get_active_profile(db)
    storage = get_storage(profile)
    storage.save(data, relative_path, content_type)

    doc = Document(
        vehicle_id=vehicle_id,
        filename=safe_name,
        storage_path=relative_path,
        storage_profile_id=profile.id,
        content_type=content_type,
        byte_length=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        document_type='vehicle_photo',
    )
    db.add(doc)
    try:
        db.flush()
        vehicle = db.get(Vehicle, vehicle_id)
        if vehicle.primary_photo_id is None:
            vehicle.primary_photo_id = doc.id
        db.commit()
    except Exception:
        db.rollback()
        try:
            storage.delete(relative_path)
        except Exception:
            schedule_cleanup(db, profile.id, relative_path)
            db.commit()
        raise
    db.refresh(doc)
    return {"id": doc.id, "filename": doc.filename}


@router.get("/{vehicle_id}/photos", response_model=List[VehiclePhotoResponse])
def list_vehicle_photos(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db)
    return (
        db.query(Document)
        .filter(Document.vehicle_id == vehicle_id, Document.document_type == "vehicle_photo")
        .order_by(Document.uploaded_at.desc())
        .all()
    )


@router.delete("/{vehicle_id}/photos/{photo_id}")
def delete_vehicle_photo_by_id(
    vehicle_id: int,
    photo_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db, require_write=True)
    doc = db.query(Document).filter(
        Document.id == photo_id,
        Document.vehicle_id == vehicle_id,
        Document.document_type == "vehicle_photo",
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Photo not found")
    vehicle = db.get(Vehicle, vehicle_id)
    profile_id, object_key = doc.storage_profile_id, doc.storage_path
    if vehicle.primary_photo_id == doc.id:
        successor = _photo_successor(db, vehicle_id, doc.id)
        vehicle.primary_photo_id = successor.id if successor else None
    db.delete(doc)
    if profile_id:
        cleanup = schedule_cleanup(db, profile_id, object_key)
    db.commit()
    if profile_id:
        from app.services.storage_cleanup import run_cleanup
        run_cleanup(db, cleanup.id)
    return {"message": "Photo deleted"}


@router.get("/{vehicle_id}/photo")
def get_vehicle_photo(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db)
    vehicle = db.get(Vehicle, vehicle_id)
    doc = db.get(Document, vehicle.primary_photo_id) if vehicle.primary_photo_id else None
    if not doc:
        raise HTTPException(status_code=404, detail="No photo")
    try:
        content = get_storage_for_profile(db, doc.storage_profile_id).load(doc.storage_path)
    except Exception:
        raise HTTPException(status_code=404, detail="Photo not found in storage")
    media_type = doc.content_type or _media_type(doc.filename or '')
    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(doc.filename or 'photo', safe='')}",
                 "X-Content-Type-Options": "nosniff"},
    )


@router.delete("/{vehicle_id}/photo")
def delete_vehicle_photo(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db, require_write=True)
    vehicle = db.get(Vehicle, vehicle_id)
    doc = db.get(Document, vehicle.primary_photo_id) if vehicle.primary_photo_id else None
    if not doc:
        raise HTTPException(status_code=404, detail="No photo")
    profile_id, object_key = doc.storage_profile_id, doc.storage_path
    successor = _photo_successor(db, vehicle_id, doc.id)
    vehicle.primary_photo_id = successor.id if successor else None
    db.delete(doc)
    if profile_id:
        cleanup = schedule_cleanup(db, profile_id, object_key)
    db.commit()
    if profile_id:
        from app.services.storage_cleanup import run_cleanup
        run_cleanup(db, cleanup.id)
    return {"message": "Photo deleted"}
