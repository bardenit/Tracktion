from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import User, VehiclePart
from app.schemas import VehiclePartCreate, VehiclePartUpdate, VehiclePartResponse
from app.auth import get_current_user
from app.deps import check_vehicle_access

router = APIRouter()


@router.post("/{vehicle_id}/parts", response_model=VehiclePartResponse)
def create_part(
    vehicle_id: int,
    part_data: VehiclePartCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db)
    part = VehiclePart(vehicle_id=vehicle_id, **part_data.model_dump())
    db.add(part)
    db.commit()
    db.refresh(part)
    return part


@router.get("/{vehicle_id}/parts", response_model=List[VehiclePartResponse])
def list_parts(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db)
    return db.query(VehiclePart).filter(VehiclePart.vehicle_id == vehicle_id).order_by(VehiclePart.category, VehiclePart.name).all()


@router.put("/{vehicle_id}/parts/{part_id}", response_model=VehiclePartResponse)
def update_part(
    vehicle_id: int,
    part_id: int,
    part_data: VehiclePartUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db)
    part = db.query(VehiclePart).filter(VehiclePart.id == part_id, VehiclePart.vehicle_id == vehicle_id).first()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    for field, value in part_data.model_dump(exclude_unset=True).items():
        setattr(part, field, value)
    db.commit()
    db.refresh(part)
    return part


@router.delete("/{vehicle_id}/parts/{part_id}")
def delete_part(
    vehicle_id: int,
    part_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db)
    part = db.query(VehiclePart).filter(VehiclePart.id == part_id, VehiclePart.vehicle_id == vehicle_id).first()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    db.delete(part)
    db.commit()
    return {"message": "Part deleted"}
