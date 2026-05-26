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
    ]
    with engine.connect() as conn:
        for stmt in new_columns:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                conn.rollback()
