from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.data_config import get_database_url
from app.config import settings

SQLALCHEMY_DATABASE_URL = get_database_url()

connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=not SQLALCHEMY_DATABASE_URL.startswith("sqlite"),
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations():
    from sqlalchemy import text
    is_pg = not SQLALCHEMY_DATABASE_URL.startswith("sqlite")
    ts_type = "TIMESTAMP" if is_pg else "DATETIME"
    add_col = "ADD COLUMN IF NOT EXISTS" if is_pg else "ADD COLUMN"
    new_columns = [
        f"ALTER TABLE users {add_col} failed_login_attempts INTEGER DEFAULT 0",
        f"ALTER TABLE users {add_col} last_failed_login_at {ts_type}",
        f"ALTER TABLE users {add_col} locked_until {ts_type}",
        f"ALTER TABLE maintenance_reminders {add_col} target_mileage FLOAT",
        f"ALTER TABLE maintenance_reminders {add_col} reminder_miles INTEGER",
        f"ALTER TABLE vehicles {add_col} license_plate VARCHAR(20)",
        f"ALTER TABLE expenses {add_col} expires_on DATE",
        f"ALTER TABLE vehicle_parts {add_col} needs_order BOOLEAN DEFAULT FALSE",
        f"ALTER TABLE fuel_entries {add_col} octane INTEGER",
        f"ALTER TABLE vehicles {add_col} tank_size_gallons FLOAT",
        f"ALTER TABLE vehicle_parts {add_col} order_status VARCHAR(20)",
        f"ALTER TABLE vehicles {add_col} recalls_seen {'JSON' if is_pg else 'TEXT'}",
        f"ALTER TABLE vehicles {add_col} recalls_cache {'JSON' if is_pg else 'TEXT'}",
        f"ALTER TABLE documents {add_col} maintenance_entry_id INTEGER",
        # Repair rows poisoned by the is_overdue None bug (list endpoint 500)
        "UPDATE maintenance_reminders SET is_overdue = FALSE WHERE is_overdue IS NULL",
        # Migrate existing needs_order=true rows
        "UPDATE vehicle_parts SET order_status = 'needs_order' WHERE needs_order = true AND order_status IS NULL",

        f"""CREATE TABLE IF NOT EXISTS inspection_items (
            id {"SERIAL" if is_pg else "INTEGER"} PRIMARY KEY {"" if is_pg else "AUTOINCREMENT"},
            vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
            name VARCHAR(255) NOT NULL,
            category VARCHAR(100) NOT NULL DEFAULT 'general',
            last_checked_at {ts_type},
            order_index INTEGER DEFAULT 0,
            created_at {ts_type} DEFAULT CURRENT_TIMESTAMP
        )""",
        f"""CREATE TABLE IF NOT EXISTS tire_events (
            id {"SERIAL" if is_pg else "INTEGER"} PRIMARY KEY {"" if is_pg else "AUTOINCREMENT"},
            vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
            event_type VARCHAR(50) NOT NULL,
            date DATE NOT NULL,
            mileage FLOAT NOT NULL,
            brand VARCHAR(100),
            size VARCHAR(50),
            pressure_fl FLOAT,
            pressure_fr FLOAT,
            pressure_rl FLOAT,
            pressure_rr FLOAT,
            tread_fl FLOAT,
            tread_fr FLOAT,
            tread_rl FLOAT,
            tread_rr FLOAT,
            notes TEXT,
            created_at {ts_type} DEFAULT CURRENT_TIMESTAMP
        )""",
    ]
    with engine.connect() as conn:
        for stmt in new_columns:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                conn.rollback()
