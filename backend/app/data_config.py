import json
import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "/app/data"))
CONFIG_FILE = DATA_DIR / "config.json"


def _default_db_url() -> str:
    return f"sqlite:///{DATA_DIR}/tracktion.db"


def _storage_from_env() -> dict | None:
    t = os.environ.get("STORAGE_TYPE", "").lower()
    if t == "s3":
        return {
            "type": "s3",
            "endpoint": os.environ.get("STORAGE_S3_ENDPOINT", ""),
            "bucket": os.environ.get("STORAGE_S3_BUCKET", ""),
            "region": os.environ.get("STORAGE_S3_REGION", "us-east-1"),
            "access_key": os.environ.get("STORAGE_S3_ACCESS_KEY", ""),
            "secret_key": os.environ.get("STORAGE_S3_SECRET_KEY", ""),
        }
    if t == "webdav":
        return {
            "type": "webdav",
            "url": os.environ.get("STORAGE_WEBDAV_URL", ""),
            "username": os.environ.get("STORAGE_WEBDAV_USERNAME", ""),
            "password": os.environ.get("STORAGE_WEBDAV_PASSWORD", ""),
            "path": os.environ.get("STORAGE_WEBDAV_PATH", "/tracktion"),
        }
    return None


def _backfill_from_env(config: dict) -> dict:
    """Fill any missing sections from environment variables."""
    if "storage" not in config:
        env_storage = _storage_from_env()
        if env_storage:
            config["storage"] = env_storage
    if "integrations" not in config:
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if key:
            config["integrations"] = {"anthropic_api_key": key}
    return config


def get_config() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            config = json.loads(CONFIG_FILE.read_text())
            return _backfill_from_env(config)
        except Exception:
            pass
    env_db_url = os.environ.get("DATABASE_URL") or _default_db_url()
    if "postgresql" in env_db_url or "postgres" in env_db_url:
        db_type = "postgresql"
    elif "mysql" in env_db_url:
        db_type = "mysql"
    else:
        db_type = "sqlite"
    config: dict = {"database": {"type": db_type, "url": env_db_url}}
    return _backfill_from_env(config)


def save_config(config: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
    try:
        CONFIG_FILE.chmod(0o600)
    except Exception:
        pass


def get_database_url() -> str:
    # Config file takes priority
    if CONFIG_FILE.exists():
        url = get_config().get("database", {}).get("url")
        if url:
            return url
    # Fall back to DATABASE_URL env var (existing deployments)
    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        return env_url
    # Default to SQLite
    return _default_db_url()
