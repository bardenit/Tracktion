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


DEFAULT_OLLAMA_URL = "http://10.10.10.10:11434"
DEFAULT_OLLAMA_MODEL = "qwen3.5:4b"


def _seed_ocr_providers(anthropic_key: str) -> dict:
    """Default provider list. Anthropic is included only if a key is already known,
    so an existing install keeps working without reconfiguration."""
    providers = [{
        "id": "ollama-local",
        "type": "ollama",
        "label": "Local Ollama",
        "base_url": DEFAULT_OLLAMA_URL,
        "model": DEFAULT_OLLAMA_MODEL,
        "api_key": "",
    }]
    if anthropic_key:
        providers.append({
            "id": "anthropic",
            "type": "anthropic",
            "label": "Anthropic",
            "base_url": "",
            "model": "claude-sonnet-5",
            "api_key": anthropic_key,
        })
    return {"active": "ollama-local", "providers": providers}


def _backfill_from_env(config: dict) -> dict:
    """Fill any missing sections from environment variables."""
    if "storage" not in config:
        env_storage = _storage_from_env()
        if env_storage:
            config["storage"] = env_storage
    integrations = config.setdefault("integrations", {})
    if "ocr" not in integrations:
        # Migration path: the pre-provider shape stored a single Anthropic key.
        key = integrations.get("anthropic_api_key", "") or os.environ.get("ANTHROPIC_API_KEY", "")
        integrations["ocr"] = _seed_ocr_providers(key)
    return config


def get_ocr_settings() -> dict:
    """Provider list and active selection, seeded on first read."""
    return get_config().get("integrations", {}).get("ocr", _seed_ocr_providers(""))


def get_ocr_provider(provider_id: str = "") -> dict:
    """Resolve a provider config by id, defaulting to the active one.

    The id is always resolved against stored config — a caller-supplied base URL
    is never honoured, which keeps the OCR endpoints from becoming an SSRF
    primitive against the internal network.
    """
    settings = get_ocr_settings()
    providers = settings.get("providers", [])
    wanted = provider_id or settings.get("active", "")
    for provider in providers:
        if provider.get("id") == wanted:
            return provider
    if provider_id:
        return {}
    return providers[0] if providers else {}


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
