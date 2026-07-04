from pydantic import BaseModel, EmailStr, field_validator, Field
from typing import Optional, List, Literal
from datetime import date, datetime


# Auth Schemas
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator('password')
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(..., max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: int
    email: str
    created_at: datetime

    class Config:
        from_attributes = True


# Vehicle Schemas
class VehicleCreate(BaseModel):
    nickname: Optional[str] = Field(None, max_length=100)
    vehicle_type: str = Field("vehicle", max_length=50)
    make: str = Field(..., max_length=255)
    model: str = Field(..., max_length=255)
    year: int
    vin: Optional[str] = Field(None, max_length=17)
    license_plate: Optional[str] = Field(None, max_length=20)
    current_mileage: float = 0
    fuel_type: str = Field("gasoline", max_length=50)
    axle_count: Optional[int] = None


class VehicleUpdate(BaseModel):
    nickname: Optional[str] = Field(None, max_length=100)
    vehicle_type: Optional[str] = Field(None, max_length=50)
    make: Optional[str] = Field(None, max_length=255)
    model: Optional[str] = Field(None, max_length=255)
    year: Optional[int] = None
    vin: Optional[str] = Field(None, max_length=17)
    license_plate: Optional[str] = Field(None, max_length=20)
    current_mileage: Optional[float] = None
    fuel_type: Optional[str] = Field(None, max_length=50)
    axle_count: Optional[int] = None
    tank_size_gallons: Optional[float] = None
    specs_overrides: Optional[dict] = None


class VINRequest(BaseModel):
    vin: str = Field(..., max_length=17)


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
    license_plate: Optional[str] = None
    current_mileage: float
    fuel_type: str
    axle_count: Optional[int] = None
    tank_size_gallons: Optional[float] = None
    nhtsa_data: Optional[dict] = None
    specs_overrides: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


VALID_ORDER_STATUSES = {'needs_order', 'ordered', 'received'}


class VehiclePartCreate(BaseModel):
    name: str = Field(..., max_length=255)
    part_number: Optional[str] = Field(None, max_length=100)
    brand: Optional[str] = Field(None, max_length=255)
    category: str = Field("other", max_length=50)
    notes: Optional[str] = Field(None, max_length=1000)
    order_status: Optional[str] = None

    @field_validator('order_status')
    @classmethod
    def validate_order_status(cls, v):
        if v is not None and v not in VALID_ORDER_STATUSES:
            raise ValueError(f'order_status must be one of {VALID_ORDER_STATUSES}')
        return v


class VehiclePartUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    part_number: Optional[str] = Field(None, max_length=100)
    brand: Optional[str] = Field(None, max_length=255)
    category: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = Field(None, max_length=1000)
    order_status: Optional[str] = None

    @field_validator('order_status')
    @classmethod
    def validate_order_status(cls, v):
        if v is not None and v not in VALID_ORDER_STATUSES:
            raise ValueError(f'order_status must be one of {VALID_ORDER_STATUSES}')
        return v


class VehiclePartResponse(BaseModel):
    id: int
    vehicle_id: int
    name: str
    part_number: Optional[str] = None
    brand: Optional[str] = None
    category: str
    notes: Optional[str] = None
    order_status: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Fuel Entry Schemas
class FuelEntryCreate(BaseModel):
    date: date
    mileage: float
    gallons: float
    cost: float
    location: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = Field(None, max_length=1000)
    octane: Optional[int] = None


class FuelEntryResponse(BaseModel):
    id: int
    vehicle_id: int
    date: date
    mileage: float
    gallons: float
    cost: float
    location: Optional[str]
    notes: Optional[str]
    octane: Optional[int] = None
    mpg: Optional[float]
    cost_per_mile: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


# Maintenance Entry Schemas
class MaintenanceEntryCreate(BaseModel):
    date: date
    mileage: float
    type: str = Field(..., max_length=255)
    cost: float
    service_provider: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = Field(None, max_length=1000)


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
    category: str = Field(..., max_length=100)
    amount: float
    date: date
    description: str = Field(..., max_length=500)
    expires_on: Optional[date] = None


class ExpenseResponse(BaseModel):
    id: int
    vehicle_id: int
    category: str
    amount: float
    date: date
    description: str
    expires_on: Optional[date] = None
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
    maintenance_entry_id: Optional[int] = None
    filename: str
    document_type: str
    ocr_text: Optional[str]
    uploaded_at: datetime

    class Config:
        from_attributes = True


# Maintenance Reminder Schemas
class MaintenanceReminderCreate(BaseModel):
    service_type: str = Field(..., max_length=255)
    interval_miles: Optional[float] = None
    interval_days: Optional[int] = None
    target_mileage: Optional[float] = None
    reminder_miles: Optional[int] = None


class MaintenanceReminderUpdate(BaseModel):
    service_type: Optional[str] = Field(None, max_length=255)
    interval_miles: Optional[float] = None
    interval_days: Optional[int] = None
    target_mileage: Optional[float] = None
    reminder_miles: Optional[int] = None
    last_performed_mileage: Optional[float] = None
    last_performed_date: Optional[date] = None
    next_due_mileage: Optional[float] = None
    next_due_date: Optional[date] = None


class MaintenanceReminderResponse(BaseModel):
    id: int
    vehicle_id: int
    service_type: str
    interval_miles: Optional[float]
    interval_days: Optional[int]
    target_mileage: Optional[float]
    reminder_miles: Optional[int]
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
    role: Literal["viewer", "editor"] = "viewer"


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
    destination: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = Field(None, max_length=1000)


class TripEntryUpdate(BaseModel):
    date: Optional[date] = None
    miles: Optional[float] = None
    destination: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = Field(None, max_length=1000)


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
    type: str = Field(..., max_length=50)
    host: Optional[str] = Field(None, max_length=255)
    port: Optional[int] = None
    database: Optional[str] = Field(None, max_length=255)
    username: Optional[str] = Field(None, max_length=255)
    password: Optional[str] = Field(None, max_length=255)


class DBSettingsResponse(BaseModel):
    type: str
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None


class StorageSettings(BaseModel):
    type: str = Field("local", max_length=50)
    endpoint: Optional[str] = Field(None, max_length=500)
    bucket: Optional[str] = Field(None, max_length=255)
    region: Optional[str] = Field(None, max_length=100)
    access_key: Optional[str] = Field(None, max_length=255)
    secret_key: Optional[str] = Field(None, max_length=255)
    url: Optional[str] = Field(None, max_length=500)
    username: Optional[str] = Field(None, max_length=255)
    password: Optional[str] = Field(None, max_length=255)
    path: Optional[str] = Field(None, max_length=500)


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


# Inspection Schemas
class InspectionItemCreate(BaseModel):
    name: str = Field(..., max_length=255)
    category: str = Field("general", max_length=100)
    order_index: int = 0


class InspectionItemUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    category: Optional[str] = Field(None, max_length=100)
    last_checked_at: Optional[datetime] = None
    order_index: Optional[int] = None


class InspectionItemResponse(BaseModel):
    id: int
    vehicle_id: int
    name: str
    category: str
    last_checked_at: Optional[datetime] = None
    order_index: int

    class Config:
        from_attributes = True


# Tire Event Schemas
class TireEventCreate(BaseModel):
    event_type: Literal["install", "rotation", "pressure", "tread"]
    date: date
    mileage: float
    brand: Optional[str] = Field(None, max_length=255)
    size: Optional[str] = Field(None, max_length=50)
    pressure_fl: Optional[float] = None
    pressure_fr: Optional[float] = None
    pressure_rl: Optional[float] = None
    pressure_rr: Optional[float] = None
    tread_fl: Optional[float] = None
    tread_fr: Optional[float] = None
    tread_rl: Optional[float] = None
    tread_rr: Optional[float] = None
    notes: Optional[str] = Field(None, max_length=1000)


class TireEventResponse(BaseModel):
    id: int
    vehicle_id: int
    event_type: str
    date: date
    mileage: float
    brand: Optional[str] = None
    size: Optional[str] = None
    pressure_fl: Optional[float] = None
    pressure_fr: Optional[float] = None
    pressure_rl: Optional[float] = None
    pressure_rr: Optional[float] = None
    tread_fl: Optional[float] = None
    tread_fr: Optional[float] = None
    tread_rl: Optional[float] = None
    tread_rr: Optional[float] = None
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Photo listing schema
class VehiclePhotoResponse(BaseModel):
    id: int
    filename: Optional[str]
    uploaded_at: datetime

    class Config:
        from_attributes = True
