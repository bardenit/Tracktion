from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Date, Boolean, JSON, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from app.database import Base
import enum


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True)
    password_hash = Column(String(255))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    vehicles = relationship("Vehicle", back_populates="owner")
    collaborations = relationship("VehicleCollaborator", back_populates="user")


class FuelType(str, enum.Enum):
    GASOLINE = "gasoline"
    DIESEL = "diesel"
    HYBRID = "hybrid"
    ELECTRIC = "electric"
    ETHANOL = "ethanol"


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    nickname = Column(String(100), nullable=True)
    vehicle_type = Column(String(50), default="vehicle")  # vehicle, trailer
    make = Column(String(255))
    model = Column(String(255))
    year = Column(Integer)
    vin = Column(String(17), unique=True, index=True, nullable=True)
    license_plate = Column(String(20), nullable=True)
    current_mileage = Column(Float, default=0)
    fuel_type = Column(String(50), default=FuelType.GASOLINE)
    axle_count = Column(Integer, nullable=True)
    nhtsa_data = Column(JSON, nullable=True)
    specs_overrides = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    owner = relationship("User", back_populates="vehicles")
    fuel_entries = relationship("FuelEntry", back_populates="vehicle", cascade="all, delete-orphan")
    maintenance_entries = relationship("MaintenanceEntry", back_populates="vehicle", cascade="all, delete-orphan")
    expenses = relationship("Expense", back_populates="vehicle", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="vehicle", cascade="all, delete-orphan")
    maintenance_reminders = relationship("MaintenanceReminder", back_populates="vehicle", cascade="all, delete-orphan")
    collaborators = relationship("VehicleCollaborator", back_populates="vehicle", cascade="all, delete-orphan")
    parts = relationship("VehiclePart", back_populates="vehicle", cascade="all, delete-orphan")
    trip_entries = relationship("TripEntry", back_populates="vehicle", cascade="all, delete-orphan")
    inspection_items = relationship("InspectionItem", back_populates="vehicle", cascade="all, delete-orphan")


class VehicleCollaborator(Base):
    __tablename__ = "vehicle_collaborators"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    role = Column(String(50), default="viewer")  # viewer, editor
    created_at = Column(DateTime, server_default=func.now())

    vehicle = relationship("Vehicle", back_populates="collaborators")
    user = relationship("User", back_populates="collaborations")


class FuelEntry(Base):
    __tablename__ = "fuel_entries"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), index=True)
    date = Column(Date, index=True)
    mileage = Column(Float)
    gallons = Column(Float)  # Liters or gallons
    cost = Column(Float)
    location = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    mpg = Column(Float, nullable=True)  # Calculated
    cost_per_mile = Column(Float, nullable=True)  # Calculated
    created_at = Column(DateTime, server_default=func.now())

    vehicle = relationship("Vehicle", back_populates="fuel_entries")


class MaintenanceEntry(Base):
    __tablename__ = "maintenance_entries"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), index=True)
    date = Column(Date, index=True)
    mileage = Column(Float)
    type = Column(String(255))  # Oil change, tire rotation, etc.
    cost = Column(Float)
    service_provider = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    vehicle = relationship("Vehicle", back_populates="maintenance_entries")


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), index=True)
    category = Column(String(50))  # insurance, registration, repair, fuel, other
    amount = Column(Float)
    date = Column(Date, index=True)
    description = Column(String(255))
    expires_on = Column(Date, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    vehicle = relationship("Vehicle", back_populates="expenses")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), index=True)
    filename = Column(String(255))
    storage_path = Column(String(512))  # Relative path in storage backend
    ocr_text = Column(Text, nullable=True)  # Extracted text (Phase 2)
    document_type = Column(String(50))  # receipt, service, insurance, registration, warranty, other
    uploaded_at = Column(DateTime, server_default=func.now())

    vehicle = relationship("Vehicle", back_populates="documents")


class MaintenanceReminder(Base):
    __tablename__ = "maintenance_reminders"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), index=True)
    service_type = Column(String(255))
    interval_miles = Column(Float, nullable=True)
    interval_days = Column(Integer, nullable=True)
    target_mileage = Column(Float, nullable=True)   # absolute odometer target
    reminder_miles = Column(Integer, nullable=True)  # warn X miles before due
    last_performed_mileage = Column(Float, nullable=True)
    last_performed_date = Column(Date, nullable=True)
    next_due_mileage = Column(Float, nullable=True)
    next_due_date = Column(Date, nullable=True)
    is_overdue = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    vehicle = relationship("Vehicle", back_populates="maintenance_reminders")


class TripEntry(Base):
    __tablename__ = "trip_entries"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), index=True)
    date = Column(Date, index=True)
    miles = Column(Float)
    destination = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    vehicle = relationship("Vehicle", back_populates="trip_entries")


class VehiclePart(Base):
    __tablename__ = "vehicle_parts"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), index=True)
    name = Column(String(255))
    part_number = Column(String(100), nullable=True)
    brand = Column(String(100), nullable=True)
    category = Column(String(50), default="other")
    notes = Column(Text, nullable=True)
    needs_order = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    vehicle = relationship("Vehicle", back_populates="parts")


class InspectionItem(Base):
    __tablename__ = "inspection_items"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), index=True)
    name = Column(String(255))
    category = Column(String(100))
    last_checked_at = Column(DateTime, nullable=True)
    order_index = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())

    vehicle = relationship("Vehicle", back_populates="inspection_items")


__all__ = [
    "User",
    "Vehicle",
    "VehicleCollaborator",
    "FuelEntry",
    "MaintenanceEntry",
    "Expense",
    "Document",
    "MaintenanceReminder",
    "VehiclePart",
    "TripEntry",
    "InspectionItem",
]
