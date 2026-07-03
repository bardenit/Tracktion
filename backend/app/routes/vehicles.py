from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import or_
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import User, Vehicle, VehicleCollaborator, FuelEntry, MaintenanceEntry, Expense, TireEvent
from app.schemas import (
    VehicleCreate,
    VehicleUpdate,
    VehicleResponse,
    VINDecodeResponse,
    VINRequest,
    VehicleCollaboratorCreate,
    VehicleCollaboratorResponse,
)
from app.auth import get_current_user
from app.deps import check_vehicle_access
from app.services.vin_decoder import decode_vin, extract_vin_data_for_storage
from app.services.recalls import get_recalls
from app.services.report import build_vehicle_report
from app.services.nhtsa import get_safety_ratings, get_complaints, get_epa_rating

router = APIRouter()


@router.post("/", response_model=VehicleResponse)
async def create_vehicle(
    vehicle_data: VehicleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    nhtsa_data = None
    if vehicle_data.vin:
        vin_decode = await decode_vin(vehicle_data.vin)
        if vin_decode:
            nhtsa_data = extract_vin_data_for_storage(vin_decode)
            if not vehicle_data.make and vin_decode.make:
                vehicle_data.make = vin_decode.make
            if not vehicle_data.model and vin_decode.model:
                vehicle_data.model = vin_decode.model
            if not vehicle_data.year and vin_decode.year:
                vehicle_data.year = vin_decode.year
            if vin_decode.fuel_type:
                vehicle_data.fuel_type = vin_decode.fuel_type.lower()

    vehicle = Vehicle(
        user_id=current_user.id,
        nickname=vehicle_data.nickname,
        vehicle_type=vehicle_data.vehicle_type,
        make=vehicle_data.make,
        model=vehicle_data.model,
        year=vehicle_data.year,
        vin=vehicle_data.vin,
        license_plate=vehicle_data.license_plate,
        current_mileage=vehicle_data.current_mileage,
        fuel_type=vehicle_data.fuel_type,
        axle_count=vehicle_data.axle_count,
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
    collab_ids = (
        db.query(VehicleCollaborator.vehicle_id)
        .filter(VehicleCollaborator.user_id == current_user.id)
        .subquery()
    )
    return (
        db.query(Vehicle)
        .filter(or_(Vehicle.user_id == current_user.id, Vehicle.id.in_(collab_ids)))
        .all()
    )


@router.get("/vin-lookup", response_model=VINDecodeResponse)
async def vin_lookup(vin: str, current_user: User = Depends(get_current_user)):
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
    return check_vehicle_access(vehicle_id, current_user.id, db)


@router.put("/{vehicle_id}", response_model=VehicleResponse)
async def update_vehicle(
    vehicle_id: int,
    vehicle_data: VehicleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    if vehicle.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    if vehicle_data.vin and vehicle_data.vin != vehicle.vin:
        vin_decode = await decode_vin(vehicle_data.vin)
        if vin_decode:
            vehicle.nhtsa_data = extract_vin_data_for_storage(vin_decode)

    for field, value in vehicle_data.model_dump(exclude_unset=True).items():
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
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    if vehicle.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    db.delete(vehicle)
    db.commit()
    return {"message": "Vehicle deleted"}


@router.post("/{vehicle_id}/decode-vin", response_model=VINDecodeResponse)
async def decode_vehicle_vin(
    vehicle_id: int,
    body: VINRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db)
    result = await decode_vin(body.vin)
    if not result:
        raise HTTPException(status_code=400, detail="Invalid VIN or decode failed")
    return result


@router.get("/{vehicle_id}/costs")
def vehicle_costs(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db)
    fuel_entries = db.query(FuelEntry).filter(FuelEntry.vehicle_id == vehicle_id).all()
    maint_entries = db.query(MaintenanceEntry).filter(MaintenanceEntry.vehicle_id == vehicle_id).all()
    expenses = db.query(Expense).filter(Expense.vehicle_id == vehicle_id).all()

    fuel_cost = sum(e.cost for e in fuel_entries)
    maintenance_cost = sum(e.cost for e in maint_entries)
    # Fuel-category expenses would double-count fuel entries
    other_cost = sum(e.amount for e in expenses if e.category != "fuel")
    total_cost = fuel_cost + maintenance_cost + other_cost

    mileages = [e.mileage for e in fuel_entries + maint_entries if e.mileage and e.mileage > 0]
    miles_tracked = max(mileages) - min(mileages) if len(mileages) >= 2 else 0

    return {
        "fuel_cost": fuel_cost,
        "maintenance_cost": maintenance_cost,
        "other_cost": other_cost,
        "total_cost": total_cost,
        "miles_tracked": miles_tracked,
        "cost_per_mile": total_cost / miles_tracked if miles_tracked > 0 else None,
    }


@router.get("/{vehicle_id}/report")
def vehicle_report(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vehicle = check_vehicle_access(vehicle_id, current_user.id, db)
    fuel_entries = db.query(FuelEntry).filter(FuelEntry.vehicle_id == vehicle_id).all()
    maint_entries = db.query(MaintenanceEntry).filter(MaintenanceEntry.vehicle_id == vehicle_id).all()
    expenses = db.query(Expense).filter(Expense.vehicle_id == vehicle_id).all()
    tire_events = db.query(TireEvent).filter(TireEvent.vehicle_id == vehicle_id).all()

    pdf = build_vehicle_report(vehicle, fuel_entries, maint_entries, expenses, tire_events)
    filename = f"{vehicle.year}-{vehicle.make}-{vehicle.model}-report.pdf".replace(" ", "-").lower()
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{vehicle_id}/recalls")
async def vehicle_recalls(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vehicle = check_vehicle_access(vehicle_id, current_user.id, db)
    if not vehicle.make or not vehicle.model or not vehicle.year:
        return {"available": False, "count": 0, "recalls": []}
    recalls = await get_recalls(vehicle.make, vehicle.model, vehicle.year)
    if recalls is None:
        return {"available": False, "count": 0, "recalls": []}
    return {"available": True, "count": len(recalls), "recalls": recalls}


def _vehicle_specs(vehicle: Vehicle) -> dict:
    specs = dict(vehicle.nhtsa_data or {})
    specs.update(vehicle.specs_overrides or {})
    return specs


@router.get("/{vehicle_id}/safety-ratings")
async def vehicle_safety_ratings(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vehicle = check_vehicle_access(vehicle_id, current_user.id, db)
    if not vehicle.make or not vehicle.model or not vehicle.year:
        return {"available": False}
    specs = _vehicle_specs(vehicle)
    result = await get_safety_ratings(
        vehicle.make, vehicle.model, vehicle.year,
        drive_type=specs.get("drive_type"),
        cab_type=specs.get("cab_type"),
        fuel_type=specs.get("fuel_type") or vehicle.fuel_type,
    )
    if result is None:
        return {"available": False}
    return {"available": True, **result}


@router.get("/{vehicle_id}/complaints")
async def vehicle_complaints(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vehicle = check_vehicle_access(vehicle_id, current_user.id, db)
    if not vehicle.make or not vehicle.model or not vehicle.year:
        return {"available": False}
    specs = _vehicle_specs(vehicle)
    result = await get_complaints(
        vehicle.make, vehicle.model, vehicle.year,
        cab_type=specs.get("cab_type"),
        fuel_type=specs.get("fuel_type") or vehicle.fuel_type,
    )
    if result is None:
        return {"available": False}
    return {"available": True, **result}


@router.get("/{vehicle_id}/epa")
async def vehicle_epa(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vehicle = check_vehicle_access(vehicle_id, current_user.id, db)
    if not vehicle.make or not vehicle.model or not vehicle.year:
        return {"available": False}
    specs = _vehicle_specs(vehicle)
    displacement = None
    try:
        displacement = float(specs.get("engine_displacement_l"))
    except (TypeError, ValueError):
        pass
    result = await get_epa_rating(
        vehicle.make, vehicle.model, vehicle.year,
        drive_type=specs.get("drive_type"),
        displacement=displacement,
        fuel_type=specs.get("fuel_type") or vehicle.fuel_type,
    )
    if result is None:
        return {"available": False}
    return {"available": True, **result}


@router.post("/{vehicle_id}/collaborators", response_model=VehicleCollaboratorResponse)
def add_collaborator(
    vehicle_id: int,
    collab_data: VehicleCollaboratorCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    if vehicle.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    collaborator_user = db.query(User).filter(User.email == collab_data.email).first()
    if not collaborator_user:
        raise HTTPException(status_code=404, detail="User not found")
    if collaborator_user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot add yourself as collaborator")

    existing = db.query(VehicleCollaborator).filter(
        VehicleCollaborator.vehicle_id == vehicle_id,
        VehicleCollaborator.user_id == collaborator_user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="User is already a collaborator")

    collaborator = VehicleCollaborator(vehicle_id=vehicle_id, user_id=collaborator_user.id, role=collab_data.role)
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
    check_vehicle_access(vehicle_id, current_user.id, db)
    return db.query(VehicleCollaborator).filter(VehicleCollaborator.vehicle_id == vehicle_id).all()


@router.delete("/{vehicle_id}/collaborators/{collaborator_id}")
def remove_collaborator(
    vehicle_id: int,
    collaborator_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    if vehicle.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    collaborator = db.query(VehicleCollaborator).filter(VehicleCollaborator.id == collaborator_id).first()
    if not collaborator:
        raise HTTPException(status_code=404, detail="Collaborator not found")

    db.delete(collaborator)
    db.commit()
    return {"message": "Collaborator removed"}
