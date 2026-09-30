import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import create_engine, text
from app.auth import get_current_user
from app.deps import require_admin
from app.models import User, StorageProfile
from app.database import get_db
from sqlalchemy.orm import Session
from app.data_config import get_config, save_config, get_database_url, get_ocr_settings
from app.schemas import (
    DBSettings, DBSettingsResponse,
    StorageSettings, StorageSettingsResponse,
    OcrSettings, OcrSettingsResponse, OcrProviderResponse,
    OcrActiveProvider, OcrProviderTest,
)
from app.services.ocr_providers import (
    ProviderError, ProviderUnreachable, build_provider,
)


router = APIRouter(dependencies=[Depends(require_admin)])


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
        logging.warning("DB connection test failed")
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
        logging.warning("DB connection test failed during save")
        raise HTTPException(status_code=400, detail="Connection test failed. Check your settings.")
    config = get_config()
    config["database"] = {"type": s.type, "url": url, "host": s.host, "port": s.port, "database": s.database, "username": s.username}
    save_config(config)
    return {"message": "Database settings saved. Restart the container to apply.", "restart_required": True}


# ── Storage ───────────────────────────────────────────────────────────────────

@router.get("/storage", response_model=StorageSettingsResponse)
def get_storage_settings(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(StorageProfile).filter_by(is_active=True).first()
    cfg = dict(profile.configuration or {}) if profile else get_config().get("storage", {})
    storage_type = profile.backend_type if profile else cfg.get("type", "local")
    return StorageSettingsResponse(
        type=storage_type,
        endpoint=cfg.get("endpoint"),
        bucket=cfg.get("bucket"),
        region=cfg.get("region"),
        access_key=None,
        url=cfg.get("url"),
        username=cfg.get("username"),
        path=cfg.get("path"),
        has_secret=bool(cfg.get("secret_key") or cfg.get("password")),
        has_access_key=bool(cfg.get("access_key")),
    )


def _storage_configuration(s: StorageSettings, existing: dict | None = None) -> dict:
    existing = existing or {}
    entry: dict = {"type": s.type}
    if s.type == "s3":
        entry.update(endpoint=s.endpoint or "", bucket=s.bucket or "", region=s.region or "us-east-1",
                     access_key=s.access_key or existing.get("access_key", ""),
                     secret_key=s.secret_key or existing.get("secret_key", ""))
    elif s.type == "webdav":
        entry.update(url=s.url or "", username=s.username or existing.get("username", ""),
                     password=s.password or existing.get("password", ""), path=s.path or "/tracktion")
    return entry


@router.post("/storage/test")
def test_storage_connection(s: StorageSettings, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        active = db.query(StorageProfile).filter_by(is_active=True).first()
        existing = dict(active.configuration or {}) if active and active.backend_type == s.type else {}
        _build_storage_config(_storage_configuration(s, existing)).test()
        return {"success": True}
    except Exception:
        logging.warning("Storage connection test failed")
        return {"success": False, "error": "Connection failed. Check your settings."}


@router.post("/storage/migrations")
def create_storage_migration(s: StorageSettings, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services.storage_migration import create_migration
    active = db.query(StorageProfile).filter_by(is_active=True).first()
    existing = dict(active.configuration or {}) if active and active.backend_type == s.type else {}
    entry = _storage_configuration(s, existing)
    try:
        _build_storage_config(entry).test()
        migration = create_migration(db, entry)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception:
        logging.warning("Storage migration creation failed")
        raise HTTPException(status_code=400, detail="Storage candidate could not be prepared")
    return {"id": migration.id, "state": migration.state}


@router.post("/storage/migrations/{migration_id}/start")
@router.post("/storage/migrations/{migration_id}/resume")
def start_storage_migration(migration_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services.storage_migration import run_migration, migration_status
    try:
        run_migration(db, migration_id)
        return migration_status(db, migration_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/storage/migrations/{migration_id}")
def get_storage_migration(migration_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services.storage_migration import migration_status
    try:
        return migration_status(db, migration_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/storage/migrations/{migration_id}/cancel")
def cancel_storage_migration_route(migration_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services.storage_migration import cancel_migration, migration_status
    try:
        cancel_migration(db, migration_id)
        return migration_status(db, migration_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/storage/buckets")
def list_storage_buckets(s: StorageSettings, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if s.type != "s3":
        raise HTTPException(status_code=400, detail="Bucket listing is only supported for S3-compatible storage")
    try:
        import boto3
        from botocore.config import Config
        active = db.query(StorageProfile).filter_by(is_active=True).first()
        stored = dict(active.configuration or {}) if active and active.backend_type == "s3" else {}
        kwargs: dict = {
            "aws_access_key_id": s.access_key or stored.get("access_key"),
            "aws_secret_access_key": s.secret_key or stored.get("secret_key", ""),
            "region_name": s.region or "us-east-1",
            "config": Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        }
        if s.endpoint:
            kwargs["endpoint_url"] = s.endpoint
        client = boto3.client("s3", **kwargs)
        response = client.list_buckets()
        return {"buckets": [b["Name"] for b in response.get("Buckets", [])]}
    except Exception:
        logging.warning("Storage bucket listing failed")
        raise HTTPException(status_code=400, detail="Could not list buckets. Check your credentials and settings.")


def _build_storage(s: StorageSettings):
    return _build_storage_config(_storage_configuration(s))


def _build_storage_config(configuration: dict):
    from app.storage import storage_from_config
    return storage_from_config(configuration)


# ── Integrations: OCR providers ───────────────────────────────────────────────

def _mask(key: str) -> str:
    return f"...{key[-4:]}" if key else None


def _to_response(provider: dict) -> OcrProviderResponse:
    key = provider.get("api_key") or ""
    return OcrProviderResponse(
        id=provider.get("id", ""),
        type=provider.get("type", ""),
        label=provider.get("label", ""),
        model=provider.get("model", ""),
        base_url=provider.get("base_url") or None,
        api_key_set=bool(key),
        api_key_preview=_mask(key),
    )


@router.get("/integrations", response_model=OcrSettingsResponse)
def get_integrations_settings(current_user: User = Depends(get_current_user)):
    settings = get_ocr_settings()
    return OcrSettingsResponse(
        active=settings.get("active", ""),
        providers=[_to_response(p) for p in settings.get("providers", [])],
    )


@router.post("/integrations/test")
def test_integrations(s: OcrProviderTest = OcrProviderTest(), current_user: User = Depends(get_current_user)):
    settings = get_ocr_settings()
    wanted = s.id or settings.get("active", "")
    cfg = next((p for p in settings.get("providers", []) if p.get("id") == wanted), None)
    if not cfg:
        return {"success": False, "error": "No such provider."}
    try:
        return build_provider(cfg).test()
    except ProviderUnreachable as exc:
        return {"success": False, "error": f"{exc.label} is unreachable."}
    except ProviderError as exc:
        return {"success": False, "error": str(exc)}
    except Exception:
        logging.warning("OCR provider test failed", exc_info=True)
        return {"success": False, "error": "Connection failed. Check the provider settings."}


@router.post("/integrations")
def save_integrations_settings(s: OcrSettings, current_user: User = Depends(get_current_user)):
    if not any(p.id == s.active for p in s.providers):
        raise HTTPException(status_code=400, detail="The active provider is not in the list.")

    config = get_config()
    existing = {
        p.get("id"): p.get("api_key", "")
        for p in config.get("integrations", {}).get("ocr", {}).get("providers", [])
    }

    providers = []
    for p in s.providers:
        # An empty key means unchanged: the UI only ever sees a masked preview,
        # so submitting the form back must not wipe a stored secret.
        key = p.api_key if p.api_key else existing.get(p.id, "")
        providers.append({
            "id": p.id,
            "type": p.type,
            "label": p.label,
            "model": p.model,
            "base_url": p.base_url or "",
            "api_key": key,
        })

    config.setdefault("integrations", {})["ocr"] = {"active": s.active, "providers": providers}
    save_config(config)
    return {"message": "OCR provider settings saved."}


@router.post("/integrations/active")
def set_active_provider(s: OcrActiveProvider, current_user: User = Depends(get_current_user)):
    config = get_config()
    ocr = config.setdefault("integrations", {}).setdefault("ocr", get_ocr_settings())
    if not any(p.get("id") == s.id for p in ocr.get("providers", [])):
        raise HTTPException(status_code=404, detail="No such provider.")
    ocr["active"] = s.id
    save_config(config)
    return {"message": "Active OCR provider updated.", "active": s.id}
