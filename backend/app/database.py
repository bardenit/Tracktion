from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from app.data_config import get_database_url
from app.config import settings

SQLALCHEMY_DATABASE_URL = get_database_url()

connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}

is_sqlite = SQLALCHEMY_DATABASE_URL.startswith("sqlite")

pool_args = {} if is_sqlite else {
    "pool_size": 10,
    "max_overflow": 20,
    "pool_timeout": 10,
    "pool_recycle": 1800,
}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=not is_sqlite,
    echo=settings.DEBUG,
    **pool_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
