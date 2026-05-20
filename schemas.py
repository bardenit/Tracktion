from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import date, datetime


# Auth Schemas
class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str
    created_at: datetime

    class Config:
        from_attributes = True


# Vehicle Schemas
class VehicleCreate(BaseModel):
    make: str
    model: str
    year: int
    vin: Optional[str] = None
    current_mileage: float = 0
    fuel_type: str = "gasoline"


class VehicleUpdate(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    vin: Optional[str] = None
    current_mileage: Optional[float] = None
    fuel_type: Optional[str] = None


class VINDecodeResponse(BaseModel):
    vin: str
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    engine_hp: Optional[str] = None
    engine_cylinders: Optional[str] = None
    transmission_type: Optional[str] = None
    drive_type: Optional[str] = None
    fuel_type: Optional[str] = None
    doors: Optional[str] = None


class VehicleResponse(BaseModel):
    id: int
    user_id: int
    make: str
    model: str
    year: int
    vin: Optional[str]
    current_mileage: float
    fuel_type: str
    nhtsa_data: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Fuel Entry Schemas
class FuelEntryCreate(BaseModel):
    date: date
    mileage: float
    gallons: float
    cost: float
    location: Optional[str] = None
    notes: Optional[str] = None


class FuelEntryResponse(BaseModel):
    id: int
    vehicle_id: int
    date: date
    mileage: float
    gallons: float
    cost: float
    location: Optional[str]
    notes: Optional[str]
    mpg: Optional[float]
    cost_per_mile: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


# Maintenance Entry Schemas
class MaintenanceEntryCreate(BaseModel):
    date: date
    mileage: float
    type: str
    cost: float
    service_provider: Optional[str] = None
    notes: Optional[str] = None


class MaintenanceEntryResponse(BaseModel):
    id: int
    vehicle_id: int
    date: date
    mileage: float
    type: str
    cost: float
    service_provider: Optional[str]
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# Expense Schemas
class ExpenseCreate(BaseModel):
    category: str
    amount: float
    date: date
    description: str


class ExpenseResponse(BaseModel):
    id: int
    vehicle_id: int
    category: str
    amount: float
    date: date
    description: str
    created_at: datetime

    class Config:
        from_attributes = True


# Document Schemas
class DocumentCreate(BaseModel):
    document_type: str
    file: Optional[bytes] = None


class DocumentResponse(BaseModel):
    id: int
    vehicle_id: int
    filename: str
    document_type: str
    ocr_text: Optional[str]
    uploaded_at: datetime

    class Config:
        from_attributes = True


# Maintenance Reminder Schemas
class MaintenanceReminderCreate(BaseModel):
    service_type: str
    interval_miles: Optional[float] = None
    interval_days: Optional[int] = None


class MaintenanceReminderUpdate(BaseModel):
    service_type: Optional[str] = None
    interval_miles: Optional[float] = None
    interval_days: Optional[int] = None
    last_performed_mileage: Optional[float] = None
    last_performed_date: Optional[date] = None


class MaintenanceReminderResponse(BaseModel):
    id: int
    vehicle_id: int
    service_type: str
    interval_miles: Optional[float]
    interval_days: Optional[int]
    last_performed_mileage: Optional[float]
    last_performed_date: Optional[date]
    next_due_mileage: Optional[float]
    next_due_date: Optional[date]
    is_overdue: bool

    class Config:
        from_attributes = True


# Collaborator Schemas
class VehicleCollaboratorCreate(BaseModel):
    email: EmailStr
    role: str = "viewer"


class VehicleCollaboratorResponse(BaseModel):
    id: int
    vehicle_id: int
    user_id: int
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


# Stats/Analytics Schemas
class FuelStats(BaseModel):
    average_mpg: Optional[float]
    total_spent: float
    total_gallons: float
    entries_count: int


class MaintenanceStats(BaseModel):
    total_cost: float
    entries_count: int
    by_type: dict


class VehicleStats(BaseModel):
    vehicle_id: int
    make: str
    model: str
    year: int
    current_mileage: float
    fuel_stats: FuelStats
    maintenance_stats: MaintenanceStats
    total_expenses: float
