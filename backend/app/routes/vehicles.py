from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import User, Vehicle, VehicleCollaborator
from app.schemas import (
    VehicleCreate,
    VehicleUpdate,
    VehicleResponse,
    VINDecodeResponse,
    VehicleCollaboratorCreate,
    VehicleCollaboratorResponse,
)
from app.auth import get_current_user
from app.services.vin_decoder import decode_vin, extract_vin_data_for_storage

router = APIRouter()


@router.post("/", response_model=VehicleResponse)
async def create_vehicle(
    vehicle_data: VehicleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new vehicle"""
    
    # If VIN provided, decode it
    nhtsa_data = None
    if vehicle_data.vin:
        vin_decode = await decode_vin(vehicle_data.vin)
        if vin_decode:
            nhtsa_data = extract_vin_data_for_storage(vin_decode)
            # Auto-fill make, model, year if not provided
            if not vehicle_data.make and vin_decode.make:
                vehicle_data.make = vin_decode.make
            if not vehicle_data.model and vin_decode.model:
                vehicle_data.model = vin_decode.model
            if not vehicle_data.year and vin_decode.year:
                vehicle_data.year = vin_decode.year
            if vin_decode.fuel_type:
                vehicle_data.fuel_type = vin_decode.fuel_type.lower()
    
    # Create vehicle
    vehicle = Vehicle(
        user_id=current_user.id,
        make=vehicle_data.make,
        model=vehicle_data.model,
        year=vehicle_data.year,
        vin=vehicle_data.vin,
        current_mileage=vehicle_data.current_mileage,
        fuel_type=vehicle_data.fuel_type,
        nhtsa_data=nhtsa_data,
    )
    
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    
    return vehicle


@router.get("/", response_model=List[VehicleResponse])
def list_vehicles(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all vehicles owned or shared with current user"""
    
    # Get owned vehicles
    owned = db.query(Vehicle).filter(Vehicle.user_id == current_user.id).all()
    
    # Get shared vehicles
    shared_ids = (
        db.query(VehicleCollaborator.vehicle_id)
        .filter(VehicleCollaborator.user_id == current_user.id)
        .all()
    )
    shared_vehicle_ids = [v[0] for v in shared_ids]
    
    shared = (
        db.query(Vehicle)
        .filter(Vehicle.id.in_(shared_vehicle_ids))
        .all()
        if shared_vehicle_ids
        else []
    )
    
    return owned + shared


@router.get("/vin-lookup", response_model=VINDecodeResponse)
async def vin_lookup(
    vin: str,
    current_user: User = Depends(get_current_user),
):
    if len(vin) != 17:
        raise HTTPException(status_code=400, detail="VIN must be 17 characters")
    result = await decode_vin(vin)
    if not result:
        raise HTTPException(status_code=400, detail="VIN not found or invalid")
    return result


@router.get("/{vehicle_id}", response_model=VehicleResponse)
def get_vehicle(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific vehicle"""
    
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    # Check permissions
    is_owner = vehicle.user_id == current_user.id
    is_collaborator = (
        db.query(VehicleCollaborator)
        .filter(
            VehicleCollaborator.vehicle_id == vehicle_id,
            VehicleCollaborator.user_id == current_user.id,
        )
        .first()
        is not None
    )
    
    if not (is_owner or is_collaborator):
        raise HTTPException(status_code=403, detail="Access denied")
    
    return vehicle


@router.put("/{vehicle_id}", response_model=VehicleResponse)
async def update_vehicle(
    vehicle_id: int,
    vehicle_data: VehicleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a vehicle"""
    
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    # Only owner can edit
    if vehicle.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # If VIN is being updated, decode it
    if vehicle_data.vin and vehicle_data.vin != vehicle.vin:
        vin_decode = await decode_vin(vehicle_data.vin)
        if vin_decode:
            vehicle.nhtsa_data = extract_vin_data_for_storage(vin_decode)
    
    # Update fields
    update_data = vehicle_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(vehicle, field, value)
    
    db.commit()
    db.refresh(vehicle)
    
    return vehicle


@router.delete("/{vehicle_id}")
def delete_vehicle(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a vehicle"""
    
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    # Only owner can delete
    if vehicle.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    db.delete(vehicle)
    db.commit()
    
    return {"message": "Vehicle deleted"}


@router.post("/{vehicle_id}/decode-vin", response_model=VINDecodeResponse)
async def decode_vehicle_vin(
    vehicle_id: int,
    vin: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Decode a VIN for a vehicle"""
    
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    # Check permissions
    is_owner = vehicle.user_id == current_user.id
    is_collaborator = (
        db.query(VehicleCollaborator)
        .filter(
            VehicleCollaborator.vehicle_id == vehicle_id,
            VehicleCollaborator.user_id == current_user.id,
        )
        .first()
        is not None
    )
    
    if not (is_owner or is_collaborator):
        raise HTTPException(status_code=403, detail="Access denied")
    
    decode_result = await decode_vin(vin)
    
    if not decode_result:
        raise HTTPException(status_code=400, detail="Invalid VIN or decode failed")
    
    return decode_result


# Collaborator endpoints
@router.post("/{vehicle_id}/collaborators", response_model=VehicleCollaboratorResponse)
def add_collaborator(
    vehicle_id: int,
    collab_data: VehicleCollaboratorCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a collaborator to a vehicle"""
    
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    # Only owner can add collaborators
    if vehicle.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Find user by email
    collaborator_user = db.query(User).filter(User.email == collab_data.email).first()
    
    if not collaborator_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if collaborator_user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot add yourself as collaborator")
    
    # Check if already collaborator
    existing = (
        db.query(VehicleCollaborator)
        .filter(
            VehicleCollaborator.vehicle_id == vehicle_id,
            VehicleCollaborator.user_id == collaborator_user.id,
        )
        .first()
    )
    
    if existing:
        raise HTTPException(status_code=400, detail="User is already a collaborator")
    
    # Add collaborator
    collaborator = VehicleCollaborator(
        vehicle_id=vehicle_id,
        user_id=collaborator_user.id,
        role=collab_data.role,
    )
    
    db.add(collaborator)
    db.commit()
    db.refresh(collaborator)
    
    return collaborator


@router.get("/{vehicle_id}/collaborators", response_model=List[VehicleCollaboratorResponse])
def list_collaborators(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List collaborators for a vehicle"""
    
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    # Check permissions
    is_owner = vehicle.user_id == current_user.id
    is_collaborator = (
        db.query(VehicleCollaborator)
        .filter(
            VehicleCollaborator.vehicle_id == vehicle_id,
            VehicleCollaborator.user_id == current_user.id,
        )
        .first()
        is not None
    )
    
    if not (is_owner or is_collaborator):
        raise HTTPException(status_code=403, detail="Access denied")
    
    collaborators = (
        db.query(VehicleCollaborator)
        .filter(VehicleCollaborator.vehicle_id == vehicle_id)
        .all()
    )
    
    return collaborators


@router.delete("/{vehicle_id}/collaborators/{collaborator_id}")
def remove_collaborator(
    vehicle_id: int,
    collaborator_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a collaborator from a vehicle"""
    
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    # Only owner can remove collaborators
    if vehicle.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    collaborator = (
        db.query(VehicleCollaborator)
        .filter(VehicleCollaborator.id == collaborator_id)
        .first()
    )
    
    if not collaborator:
        raise HTTPException(status_code=404, detail="Collaborator not found")
    
    db.delete(collaborator)
    db.commit()
    
    return {"message": "Collaborator removed"}
