from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models import Vehicle, VehicleCollaborator


def check_vehicle_access(vehicle_id: int, user_id: int, db: Session) -> Vehicle:
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    is_collab = (
        db.query(VehicleCollaborator)
        .filter(VehicleCollaborator.vehicle_id == vehicle_id, VehicleCollaborator.user_id == user_id)
        .first() is not None
    )
    if vehicle.user_id != user_id and not is_collab:
        raise HTTPException(status_code=403, detail="Access denied")
    return vehicle
