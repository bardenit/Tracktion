from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import User, Expense
from app.schemas import ExpenseCreate, ExpenseResponse
from app.auth import get_current_user
from app.deps import check_vehicle_access

router = APIRouter()


@router.post("/{vehicle_id}/entries", response_model=ExpenseResponse)
def create_expense(
    vehicle_id: int,
    expense_data: ExpenseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db, require_write=True)
    expense = Expense(
        vehicle_id=vehicle_id,
        category=expense_data.category,
        amount=expense_data.amount,
        date=expense_data.date,
        description=expense_data.description,
        expires_on=expense_data.expires_on,
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
    check_vehicle_access(vehicle_id, current_user.id, db)
    return (
        db.query(Expense)
        .filter(Expense.vehicle_id == vehicle_id)
        .order_by(Expense.date.desc())
        .all()
    )


@router.get("/{vehicle_id}/entries/{expense_id}", response_model=ExpenseResponse)
def get_expense(
    vehicle_id: int,
    expense_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_vehicle_access(vehicle_id, current_user.id, db)
    expense = db.query(Expense).filter(Expense.id == expense_id, Expense.vehicle_id == vehicle_id).first()
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
    check_vehicle_access(vehicle_id, current_user.id, db, require_write=True)
    expense = db.query(Expense).filter(Expense.id == expense_id, Expense.vehicle_id == vehicle_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    expense.category = expense_data.category
    expense.amount = expense_data.amount
    expense.date = expense_data.date
    expense.description = expense_data.description
    expense.expires_on = expense_data.expires_on

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
    check_vehicle_access(vehicle_id, current_user.id, db, require_write=True)
    expense = db.query(Expense).filter(Expense.id == expense_id, Expense.vehicle_id == vehicle_id).first()
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
    check_vehicle_access(vehicle_id, current_user.id, db)
    expenses = db.query(Expense).filter(Expense.vehicle_id == vehicle_id).all()

    by_category: dict = {}
    for expense in expenses:
        by_category[expense.category] = by_category.get(expense.category, 0) + expense.amount

    return {
        "total": sum(e.amount for e in expenses),
        "count": len(expenses),
        "by_category": by_category,
    }
