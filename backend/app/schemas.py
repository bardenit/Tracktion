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
    nickname: Optional[str] = None
    vehicle_type: str = "vehicle"
    make: str
    model: str
    year: int
    vin: Optional[str] = None
    current_mileage: float = 0
    fuel_type: str = "gasoline"
    axle_count: Optional[int] = None


class VehicleUpdate(BaseModel):
    nickname: Optional[str] = None
    vehicle_type: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    vin: Optional[str] = None
    current_mileage: Optional[float] = None
    fuel_type: Optional[str] = None
    axle_count: Optional[int] = None
    specs_overrides: Optional[dict] = None


class VINDecodeResponse(BaseModel):
    vin: str
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    # Engine
    engine_model: Optional[str] = None
    engine_cylinders: Optional[str] = None
    engine_displacement_l: Optional[str] = None
    engine_hp: Optional[str] = None
    turbo: Optional[str] = None
    fuel_type: Optional[str] = None
    # Drivetrain
    transmission_type: Optional[str] = None
    transmission_speeds: Optional[str] = None
    drive_type: Optional[str] = None
    # Body
    body_class: Optional[str] = None
    cab_type: Optional[str] = None
    doors: Optional[str] = None
    # Trim / identity
    series: Optional[str] = None
    trim: Optional[str] = None
    gvwr: Optional[str] = None
    # Origin
    plant_city: Optional[str] = None
    plant_country: Optional[str] = None


class VehicleResponse(BaseModel):
    id: int
    user_id: int
    nickname: Optional[str] = None
    vehicle_type: str = "vehicle"
    make: str
    model: str
    year: int
    vin: Optional[str]
    current_mileage: float
    fuel_type: str
    axle_count: Optional[int] = None
    nhtsa_data: Optional[dict] = None
    specs_overrides: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


class VehiclePartCreate(BaseModel):
    name: str
    part_number: Optional[str] = None
    brand: Optional[str] = None
    category: str = "other"
    notes: Optional[str] = None


class VehiclePartUpdate(BaseModel):
    name: Optional[str] = None
    part_number: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    notes: Optional[str] = None


class VehiclePartResponse(BaseModel):
    id: int
    vehicle_id: int
    name: str
    part_number: Optional[str] = None
    brand: Optional[str] = None
    category: str
    notes: Optional[str] = None
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


# Trip Entry Schemas
class TripEntryCreate(BaseModel):
    date: date
    miles: float
    destination: Optional[str] = None
    notes: Optional[str] = None


class TripEntryUpdate(BaseModel):
    date: Optional[date] = None
    miles: Optional[float] = None
    destination: Optional[str] = None
    notes: Optional[str] = None


class TripEntryResponse(BaseModel):
    id: int
    vehicle_id: int
    date: date
    miles: float
    destination: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TripStats(BaseModel):
    total_miles: float
    trip_count: int
    last_trip_date: Optional[date] = None


# Settings Schemas
class DBSettings(BaseModel):
    type: str  # sqlite, postgresql, mysql
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None


class DBSettingsResponse(BaseModel):
    type: str
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None


class StorageSettings(BaseModel):
    type: str = "local"          # local | s3 | webdav
    # S3-compatible fields
    endpoint: Optional[str] = None
    bucket: Optional[str] = None
    region: Optional[str] = None
    access_key: Optional[str] = None
    secret_key: Optional[str] = None  # write-only
    # WebDAV fields
    url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None   # write-only
    path: Optional[str] = None


class StorageSettingsResponse(BaseModel):
    type: str
    endpoint: Optional[str] = None
    bucket: Optional[str] = None
    region: Optional[str] = None
    access_key: Optional[str] = None
    url: Optional[str] = None
    username: Optional[str] = None
    path: Optional[str] = None
    has_secret: bool = False


class IntegrationsSettings(BaseModel):
    anthropic_api_key: Optional[str] = None


class IntegrationsSettingsResponse(BaseModel):
    anthropic_api_key_set: bool
    anthropic_api_key_preview: Optional[str] = None
