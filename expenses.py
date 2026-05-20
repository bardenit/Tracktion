from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import User, Vehicle, Expense, VehicleCollaborator
from app.schemas import ExpenseCreate, ExpenseResponse
from app.auth import get_current_user

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


@router.post("/{vehicle_id}/entries", response_model=ExpenseResponse)
def create_expense(
    vehicle_id: int,
    expense_data: ExpenseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new expense"""
    
    vehicle = _check_vehicle_access(vehicle_id, current_user.id, db)
    
    expense = Expense(
        vehicle_id=vehicle_id,
        category=expense_data.category,
        amount=expense_data.amount,
        date=expense_data.date,
        description=expense_data.description,
    )
    
    db.add(expense)
    db.commit()
    db.refresh(expense)
    
    return expense


@router.get("/{vehicle_id}/entries", response_model=List[ExpenseResponse])
def list_expenses(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all expenses for a vehicle"""
    
    vehicle = _check_vehicle_access(vehicle_id, current_user.id, db)
    
    expenses = (
        db.query(Expense)
        .filter(Expense.vehicle_id == vehicle_id)
        .order_by(Expense.date.desc())
        .all()
    )
    
    return expenses


@router.get("/{vehicle_id}/entries/{expense_id}", response_model=ExpenseResponse)
def get_expense(
    vehicle_id: int,
    expense_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific expense"""
    
    vehicle = _check_vehicle_access(vehicle_id, current_user.id, db)
    
    expense = (
        db.query(Expense)
        .filter(
            Expense.id == expense_id,
            Expense.vehicle_id == vehicle_id,
        )
        .first()
    )
    
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    
    return expense


@router.put("/{vehicle_id}/entries/{expense_id}", response_model=ExpenseResponse)
def update_expense(
    vehicle_id: int,
    expense_id: int,
    expense_data: ExpenseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update an expense"""
    
    vehicle = _check_vehicle_access(vehicle_id, current_user.id, db)
    
    expense = (
        db.query(Expense)
        .filter(
            Expense.id == expense_id,
            Expense.vehicle_id == vehicle_id,
        )
        .first()
    )
    
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    
    expense.category = expense_data.category
    expense.amount = expense_data.amount
    expense.date = expense_data.date
    expense.description = expense_data.description
    
    db.commit()
    db.refresh(expense)
    
    return expense


@router.delete("/{vehicle_id}/entries/{expense_id}")
def delete_expense(
    vehicle_id: int,
    expense_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an expense"""
    
    vehicle = _check_vehicle_access(vehicle_id, current_user.id, db)
    
    expense = (
        db.query(Expense)
        .filter(
            Expense.id == expense_id,
            Expense.vehicle_id == vehicle_id,
        )
        .first()
    )
    
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    
    db.delete(expense)
    db.commit()
    
    return {"message": "Expense deleted"}


@router.get("/{vehicle_id}/stats")
def get_expense_stats(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get expense statistics for a vehicle"""
    
    vehicle = _check_vehicle_access(vehicle_id, current_user.id, db)
    
    expenses = (
        db.query(Expense)
        .filter(Expense.vehicle_id == vehicle_id)
        .all()
    )
    
    total = sum(e.amount for e in expenses)
    
    # Group by category
    by_category = {}
    for expense in expenses:
        if expense.category not in by_category:
            by_category[expense.category] = 0
        by_category[expense.category] += expense.amount
    
    return {
        "total": total,
        "count": len(expenses),
        "by_category": by_category,
    }
