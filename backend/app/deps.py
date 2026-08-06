from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from app.auth import get_current_user
from app.models import User, Vehicle, VehicleCollaborator


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Administrator access required")
    return current_user


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
