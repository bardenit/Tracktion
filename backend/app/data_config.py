import json
import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "/app/data"))
CONFIG_FILE = DATA_DIR / "config.json"


def _default_db_url() -> str:
    return f"sqlite:///{DATA_DIR}/tracktion.db"


def get_config() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
    return {"database": {"type": "sqlite", "url": _default_db_url()}}


def save_config(config: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


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
