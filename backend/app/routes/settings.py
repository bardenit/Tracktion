import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import create_engine, text
from app.auth import get_current_user
from app.models import User
from app.data_config import get_config, save_config, get_database_url
from app.schemas import (
    DBSettings, DBSettingsResponse,
    StorageSettings, StorageSettingsResponse,
    IntegrationsSettings, IntegrationsSettingsResponse,
)


router = APIRouter()


# ── Database ──────────────────────────────────────────────────────────────────

def build_db_url(s: DBSettings) -> str:
    if s.type == "sqlite":
        from app.data_config import DATA_DIR
        return f"sqlite:///{DATA_DIR}/tracktion.db"
    if s.type == "postgresql":
        return f"postgresql://{s.username}:{s.password}@{s.host}:{s.port or 5432}/{s.database}"
    if s.type == "mysql":
        return f"mysql+pymysql://{s.username}:{s.password}@{s.host}:{s.port or 3306}/{s.database}"
    raise HTTPException(status_code=400, detail=f"Unsupported database type: {s.type}")


@router.get("/db/status")
def get_db_status(current_user: User = Depends(get_current_user)):
    url = get_database_url()
    if url.startswith("sqlite"):
        return {"type": "sqlite", "display": f"SQLite — {url.replace('sqlite:///', '')}"}
    if "postgresql" in url or "postgres" in url:
        try:
            from urllib.parse import urlparse
            p = urlparse(url)
            return {"type": "postgresql", "display": f"PostgreSQL — {p.hostname}:{p.port or 5432}/{p.path.lstrip('/')}"}
        except Exception:
            return {"type": "postgresql", "display": "PostgreSQL"}
    if "mysql" in url:
        try:
            from urllib.parse import urlparse
            p = urlparse(url)
            return {"type": "mysql", "display": f"MySQL — {p.hostname}:{p.port or 3306}/{p.path.lstrip('/')}"}
        except Exception:
            return {"type": "mysql", "display": "MySQL"}
    return {"type": "unknown", "display": "Unknown"}


@router.get("/db", response_model=DBSettingsResponse)
def get_db_settings(current_user: User = Depends(get_current_user)):
    db_cfg = get_config().get("database", {})
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
        engine = create_engine(url, connect_args=connect_args)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return {"success": True}
    except Exception:
        logging.exception("DB connection test failed")
        return {"success": False, "error": "Connection failed. Check your settings."}


@router.post("/db")
def save_db_settings(s: DBSettings, current_user: User = Depends(get_current_user)):
    url = build_db_url(s)
    try:
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        engine = create_engine(url, connect_args=connect_args)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
    except Exception:
        logging.exception("DB connection test failed during save")
        raise HTTPException(status_code=400, detail="Connection test failed. Check your settings.")
    config = get_config()
    config["database"] = {"type": s.type, "url": url, "host": s.host, "port": s.port, "database": s.database, "username": s.username}
    save_config(config)
    return {"message": "Database settings saved. Restart the container to apply.", "restart_required": True}


# ── Storage ───────────────────────────────────────────────────────────────────

@router.get("/storage", response_model=StorageSettingsResponse)
def get_storage_settings(current_user: User = Depends(get_current_user)):
    cfg = get_config().get("storage", {})
    return StorageSettingsResponse(
        type=cfg.get("type", "local"),
        endpoint=cfg.get("endpoint"),
        bucket=cfg.get("bucket"),
        region=cfg.get("region"),
        access_key=cfg.get("access_key"),
        url=cfg.get("url"),
        username=cfg.get("username"),
        path=cfg.get("path"),
        has_secret=bool(cfg.get("secret_key") or cfg.get("password")),
    )


@router.post("/storage/test")
def test_storage_connection(s: StorageSettings, current_user: User = Depends(get_current_user)):
    try:
        _build_storage(s).test()
        return {"success": True}
    except Exception:
        logging.exception("Storage connection test failed")
        return {"success": False, "error": "Connection failed. Check your settings."}


@router.post("/storage")
def save_storage_settings(s: StorageSettings, current_user: User = Depends(get_current_user)):
    if s.type != "local":
        try:
            _build_storage(s).test()
        except Exception:
            logging.exception("Storage connection test failed during save")
            raise HTTPException(status_code=400, detail="Connection test failed. Check your settings.")

    config = get_config()
    existing = config.get("storage", {})

    entry: dict = {"type": s.type}
    if s.type == "s3":
        entry["endpoint"] = s.endpoint or ""
        entry["bucket"] = s.bucket or ""
        entry["region"] = s.region or "us-east-1"
        entry["access_key"] = s.access_key or ""
        entry["secret_key"] = s.secret_key or existing.get("secret_key", "")
    elif s.type == "webdav":
        entry["url"] = s.url or ""
        entry["username"] = s.username or ""
        entry["password"] = s.password or existing.get("password", "")
        entry["path"] = s.path or "/tracktion"

    config["storage"] = entry
    save_config(config)
    return {"message": "Storage settings saved. New uploads will use the updated backend immediately."}


@router.post("/storage/buckets")
def list_storage_buckets(s: StorageSettings, current_user: User = Depends(get_current_user)):
    if s.type != "s3":
        raise HTTPException(status_code=400, detail="Bucket listing is only supported for S3-compatible storage")
    try:
        import boto3
        from botocore.config import Config
        stored_secret = get_config().get("storage", {}).get("secret_key", "")
        kwargs: dict = {
            "aws_access_key_id": s.access_key,
            "aws_secret_access_key": s.secret_key or stored_secret,
            "region_name": s.region or "us-east-1",
            "config": Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        }
        if s.endpoint:
            kwargs["endpoint_url"] = s.endpoint
        client = boto3.client("s3", **kwargs)
        response = client.list_buckets()
        return {"buckets": [b["Name"] for b in response.get("Buckets", [])]}
    except Exception:
        logging.exception("Storage bucket listing failed")
        raise HTTPException(status_code=400, detail="Could not list buckets. Check your credentials and settings.")


def _build_storage(s: StorageSettings):
    from app.storage import LocalStorage, S3Storage, WebDAVStorage
    if s.type == "s3":
        return S3Storage({
            "endpoint": s.endpoint, "bucket": s.bucket, "region": s.region,
            "access_key": s.access_key, "secret_key": s.secret_key,
        })
    if s.type == "webdav":
        return WebDAVStorage({"url": s.url, "username": s.username, "password": s.password, "path": s.path})
    return LocalStorage()


# ── Integrations ──────────────────────────────────────────────────────────────

@router.get("/integrations", response_model=IntegrationsSettingsResponse)
def get_integrations_settings(current_user: User = Depends(get_current_user)):
    cfg = get_config().get("integrations", {})
    key = cfg.get("anthropic_api_key", "")
    return IntegrationsSettingsResponse(
        anthropic_api_key_set=bool(key),
        anthropic_api_key_preview=f"...{key[-4:]}" if key else None,
    )


@router.post("/integrations/test")
def test_integrations(s: IntegrationsSettings = IntegrationsSettings(), current_user: User = Depends(get_current_user)):
    key = s.anthropic_api_key or get_config().get("integrations", {}).get("anthropic_api_key", "")
    if not key:
        return {"success": False, "error": "No API key configured"}
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}],
        )
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/integrations")
def save_integrations_settings(s: IntegrationsSettings, current_user: User = Depends(get_current_user)):
    config = get_config()
    existing = config.get("integrations", {})
    config["integrations"] = {
        "anthropic_api_key": s.anthropic_api_key or existing.get("anthropic_api_key", ""),
    }
    save_config(config)
    return {"message": "Integration settings saved."}
