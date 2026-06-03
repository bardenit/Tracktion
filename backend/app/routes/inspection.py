from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import User, InspectionItem
from app.schemas import InspectionItemCreate, InspectionItemUpdate, InspectionItemResponse
from app.auth import get_current_user
from app.deps import check_vehicle_access

router = APIRouter()

VEHICLE_DEFAULTS = [
    ("Tires", "Tire pressure – all four"),
    ("Tires", "Tire condition & tread depth"),
    ("Fluids", "Oil level"),
    ("Fluids", "Coolant level"),
    ("Fluids", "Brake fluid"),
    ("Fluids", "Windshield washer fluid"),
    ("Lights", "Headlights"),
    ("Lights", "Brake lights"),
    ("Lights", "Turn signals"),
    ("Lights", "Hazard lights"),
    ("Safety", "Mirrors adjusted"),
    ("Safety", "Horn"),
    ("Safety", "Wipers"),
    ("Safety", "Seat belts"),
]

TRAILER_DEFAULTS = [
    ("Hitch", "Coupler/hitch secured"),
    ("Hitch", "Safety chains crossed & connected"),
    ("Hitch", "Breakaway cable attached"),
    ("Lights", "Running lights"),
    ("Lights", "Brake lights"),
    ("Lights", "Turn signals"),
    ("Tires", "Tire condition"),
    ("Tires", "Tire pressure"),
    ("Tires", "Lug nuts torqued"),
    ("Structure", "Load secured"),
    ("Structure", "Floor/decking condition"),
    ("Structure", "Axle seals – no leaks"),
    ("Equipment", "Spare tire present"),
    ("Equipment", "Jack present"),
]


@router.get("/{vehicle_id}/items", response_model=List[InspectionItemResponse])
def list_inspection_items(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vehicle = check_vehicle_access(vehicle_id, current_user.id, db)
    items = (
        db.query(InspectionItem)
        .filter(InspectionItem.vehicle_id == vehicle_id)
        .order_by(InspectionItem.order_index, InspectionItem.id)
        .all()
    )
    if not items:
        defaults = TRAILER_DEFAULTS if vehicle.vehicle_type == "trailer" else VEHICLE_DEFAULTS
        for i, (category, name) in enumerate(defaults):
            db.add(InspectionItem(vehicle_id=vehicle_id, name=name, category=category, order_index=i))
        db.commit()
        items = (
            db.query(InspectionItem)
            .filter(InspectionItem.vehicle_id == vehicle_id)
            .order_by(InspectionItem.order_index, InspectionItem.id)
            .all()
        )
    return items


@router.post("/{vehicle_id}/items", response_model=InspectionItemResponse)
def create_inspection_item(
    vehicle_id: int,
    item_data: InspectionItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db)
    item = InspectionItem(vehicle_id=vehicle_id, **item_data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{vehicle_id}/items/{item_id}", response_model=InspectionItemResponse)
def update_inspection_item(
    vehicle_id: int,
    item_id: int,
    item_data: InspectionItemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db)
    item = db.query(InspectionItem).filter(
        InspectionItem.id == item_id, InspectionItem.vehicle_id == vehicle_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    for field, value in item_data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.post("/{vehicle_id}/items/{item_id}/check", response_model=InspectionItemResponse)
def check_inspection_item(
    vehicle_id: int,
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db)
    item = db.query(InspectionItem).filter(
        InspectionItem.id == item_id, InspectionItem.vehicle_id == vehicle_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    item.last_checked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return item


@router.post("/{vehicle_id}/reset")
def reset_inspection(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db)
    db.query(InspectionItem).filter(InspectionItem.vehicle_id == vehicle_id).update(
        {InspectionItem.last_checked_at: None}
    )
    db.commit()
    return {"message": "Inspection reset"}


@router.delete("/{vehicle_id}/items/{item_id}")
def delete_inspection_item(
    vehicle_id: int,
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db)
    item = db.query(InspectionItem).filter(
        InspectionItem.id == item_id, InspectionItem.vehicle_id == vehicle_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()
    return {"message": "Item deleted"}
