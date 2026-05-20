from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import os
from datetime import datetime
from app.database import get_db
from app.models import User, Vehicle, Document, VehicleCollaborator
from app.schemas import DocumentResponse
from app.auth import get_current_user
from app.config import settings

router = APIRouter()


def _check_vehicle_access(vehicle_id: int, user_id: int, db: Session) -> Vehicle:
    """Helper to check if user has access to vehicle"""
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    is_owner = vehicle.user_id == user_id
    is_collaborator = (
        db.query(VehicleCollaborator)
        .filter(
            VehicleCollaborator.vehicle_id == vehicle_id,
            VehicleCollaborator.user_id == user_id,
        )
        .first()
        is not None
    )
    
    if not (is_owner or is_collaborator):
        raise HTTPException(status_code=403, detail="Access denied")
    
    return vehicle


def _save_uploaded_file(
    file: UploadFile,
    vehicle_id: int,
    user_id: int,
) -> str:
    """
    Save an uploaded file to storage backend
    Returns the storage path relative to storage root
    """
    
    # Validate file size
    max_size = 20 * 1024 * 1024  # 20MB
    if file.size and file.size > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {max_size / 1024 / 1024}MB",
        )
    
    # Validate file type
    allowed_types = {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/webp",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed: PDF, Images, Word docs",
        )
    
    # Generate safe filename
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    original_name = file.filename.replace(" ", "_")
    safe_filename = f"{timestamp}_{original_name}"
    
    # Storage path
    relative_path = f"user_{user_id}/vehicle_{vehicle_id}/{safe_filename}"
    
    # For local storage (Phase 1)
    if settings.STORAGE_TYPE == "local":
        full_path = os.path.join(settings.LOCAL_STORAGE_PATH, relative_path)
        
        # Create directories
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # Save file
        with open(full_path, "wb") as f:
            content = file.file.read()
            f.write(content)
    
    # Phase 2: S3, B2, MinIO support will be added
    
    return relative_path


@router.post("/{vehicle_id}/documents", response_model=DocumentResponse)
async def upload_document(
    vehicle_id: int,
    document_type: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a document for a vehicle"""
    
    vehicle = _check_vehicle_access(vehicle_id, current_user.id, db)
    
    # Save file
    storage_path = _save_uploaded_file(file, vehicle_id, current_user.id)
    
    # Create document record
    document = Document(
        vehicle_id=vehicle_id,
        filename=file.filename,
        storage_path=storage_path,
        document_type=document_type,
        ocr_text=None,  # Will be filled in Phase 2
    )
    
    db.add(document)
    db.commit()
    db.refresh(document)
    
    return document


@router.get("/{vehicle_id}/documents", response_model=List[DocumentResponse])
def list_documents(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all documents for a vehicle"""
    
    vehicle = _check_vehicle_access(vehicle_id, current_user.id, db)
    
    documents = (
        db.query(Document)
        .filter(Document.vehicle_id == vehicle_id)
        .order_by(Document.uploaded_at.desc())
        .all()
    )
    
    return documents


@router.get("/{vehicle_id}/documents/{document_id}", response_model=DocumentResponse)
def get_document(
    vehicle_id: int,
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific document"""
    
    vehicle = _check_vehicle_access(vehicle_id, current_user.id, db)
    
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.vehicle_id == vehicle_id,
        )
        .first()
    )
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return document


@router.delete("/{vehicle_id}/documents/{document_id}")
def delete_document(
    vehicle_id: int,
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a document"""
    
    vehicle = _check_vehicle_access(vehicle_id, current_user.id, db)
    
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.vehicle_id == vehicle_id,
        )
        .first()
    )
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete file from storage
    if settings.STORAGE_TYPE == "local":
        full_path = os.path.join(settings.LOCAL_STORAGE_PATH, document.storage_path)
        if os.path.exists(full_path):
            os.remove(full_path)
    
    # Delete from database
    db.delete(document)
    db.commit()
    
    return {"message": "Document deleted"}


@router.get("/{vehicle_id}/documents/{document_id}/download")
def download_document(
    vehicle_id: int,
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download a document (Phase 1: returns path, Phase 2: returns file)"""
    
    vehicle = _check_vehicle_access(vehicle_id, current_user.id, db)
    
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.vehicle_id == vehicle_id,
        )
        .first()
    )
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Phase 1: Return metadata with presigned URL
    # Phase 2: Will generate actual presigned URL or download file
    
    return {
        "filename": document.filename,
        "storage_path": document.storage_path,
        "type": document.document_type,
        "uploaded_at": document.uploaded_at,
    }


@router.get("/{vehicle_id}/documents/by-type/{document_type}", response_model=List[DocumentResponse])
def list_documents_by_type(
    vehicle_id: int,
    document_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List documents of a specific type for a vehicle"""
    
    vehicle = _check_vehicle_access(vehicle_id, current_user.id, db)
    
    documents = (
        db.query(Document)
        .filter(
            Document.vehicle_id == vehicle_id,
            Document.document_type == document_type,
        )
        .order_by(Document.uploaded_at.desc())
        .all()
    )
    
    return documents
