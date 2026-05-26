from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import create_engine, text
from app.auth import get_current_user
from app.models import User
from app.data_config import get_config, save_config
from app.schemas import DBSettings, DBSettingsResponse

router = APIRouter()


def build_db_url(s: DBSettings) -> str:
    if s.type == "sqlite":
        from app.data_config import DATA_DIR
        return f"sqlite:///{DATA_DIR}/tracktion.db"
    if s.type == "postgresql":
        return f"postgresql://{s.username}:{s.password}@{s.host}:{s.port or 5432}/{s.database}"
    if s.type == "mysql":
        return f"mysql+pymysql://{s.username}:{s.password}@{s.host}:{s.port or 3306}/{s.database}"
    raise HTTPException(status_code=400, detail=f"Unsupported database type: {s.type}")


@router.get("/db", response_model=DBSettingsResponse)
def get_db_settings(current_user: User = Depends(get_current_user)):
    config = get_config()
    db_cfg = config.get("database", {})
    return DBSettingsResponse(
        type=db_cfg.get("type", "sqlite"),
        host=db_cfg.get("host"),
        port=db_cfg.get("port"),
        database=db_cfg.get("database"),
        username=db_cfg.get("username"),
    )


@router.post("/db/test")
def test_db_connection(s: DBSettings, current_user: User = Depends(get_current_user)):
    try:
        url = build_db_url(s)
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        test_engine = create_engine(url, connect_args=connect_args)
        with test_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        test_engine.dispose()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/db")
def save_db_settings(s: DBSettings, current_user: User = Depends(get_current_user)):
    url = build_db_url(s)
    # Test before saving
    try:
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        test_engine = create_engine(url, connect_args=connect_args)
        with test_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        test_engine.dispose()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Connection failed: {e}")

    config = get_config()
    config["database"] = {
        "type": s.type,
        "url": url,
        "host": s.host,
        "port": s.port,
        "database": s.database,
        "username": s.username,
    }
    save_config(config)
    return {"message": "Database settings saved. Restart the container to apply.", "restart_required": True}
