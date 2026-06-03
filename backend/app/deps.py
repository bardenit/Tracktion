from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models import Vehicle, VehicleCollaborator


def check_vehicle_access(vehicle_id: int, user_id: int, db: Session, require_write: bool = False) -> Vehicle:
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    if vehicle.user_id == user_id:
        return vehicle
    collab = (
        db.query(VehicleCollaborator)
        .filter(VehicleCollaborator.vehicle_id == vehicle_id, VehicleCollaborator.user_id == user_id)
        .first()
    )
    if not collab:
        raise HTTPException(status_code=403, detail="Access denied")
    if require_write and collab.role == "viewer":
        raise HTTPException(status_code=403, detail="Write access required")
    return vehicle
