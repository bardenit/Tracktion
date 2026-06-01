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
    new_columns = [
        "ALTER TABLE maintenance_reminders ADD COLUMN target_mileage FLOAT",
        "ALTER TABLE maintenance_reminders ADD COLUMN reminder_miles INTEGER",
        "ALTER TABLE vehicles ADD COLUMN license_plate VARCHAR(20)",
        "ALTER TABLE expenses ADD COLUMN expires_on DATE",
        "ALTER TABLE vehicle_parts ADD COLUMN needs_order BOOLEAN DEFAULT FALSE",
        "ALTER TABLE fuel_entries ADD COLUMN octane INTEGER",
        "ALTER TABLE vehicles ADD COLUMN tank_size_gallons FLOAT",
        "ALTER TABLE vehicles ADD COLUMN smartcar_vehicle_id VARCHAR(255)",
        "ALTER TABLE vehicles ADD COLUMN smartcar_user_id VARCHAR(255)",
        "ALTER TABLE vehicles ADD COLUMN smartcar_access_token TEXT",
        "ALTER TABLE vehicles ADD COLUMN smartcar_refresh_token TEXT",
        "ALTER TABLE vehicles ADD COLUMN smartcar_token_expires_at TIMESTAMP",
        "ALTER TABLE vehicles ADD COLUMN smartcar_last_synced_at TIMESTAMP",
        """CREATE TABLE IF NOT EXISTS inspection_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
            name VARCHAR(255) NOT NULL,
            category VARCHAR(100) NOT NULL DEFAULT 'general',
            last_checked_at DATETIME,
            order_index INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS tire_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
    ]
    with engine.connect() as conn:
        for stmt in new_columns:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                conn.rollback()
