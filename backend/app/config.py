import logging
import os
import secrets
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings

from app.data_config import DATA_DIR


LEGACY_DEFAULT_SECRET = "change-me-in-production"
JWT_SECRET_FILE = DATA_DIR / ".jwt_secret"


def load_or_create_jwt_secret(path: Path = JWT_SECRET_FILE) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        secret = path.read_text().strip()
    except FileNotFoundError:
        secret = secrets.token_urlsafe(48)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            secret = path.read_text().strip()
        else:
            with os.fdopen(fd, "w") as secret_file:
                secret_file.write(secret)
    if not secret:
        raise RuntimeError(f"Persisted JWT secret is empty: {path}")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return secret


def resolve_jwt_secret(path: Path = JWT_SECRET_FILE) -> str:
    explicit_secret = os.environ.get("JWT_SECRET_KEY", "").strip()
    if explicit_secret and explicit_secret != LEGACY_DEFAULT_SECRET:
        return explicit_secret
    return load_or_create_jwt_secret(path)


class Settings(BaseSettings):
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    LOCAL_STORAGE_PATH: str = "/app/data/documents"

    ENVIRONMENT: str = "production"
    DEBUG: bool = False
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # Default open so it works behind any reverse proxy; override via env var
    CORS_ORIGINS: List[str] = ["*"]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings(JWT_SECRET_KEY=resolve_jwt_secret())


def validate_production_secret(config: Settings) -> None:
    secret = config.JWT_SECRET_KEY.strip()
    if not secret:
        raise RuntimeError("JWT_SECRET_KEY must not be empty")
    if not config.DEBUG and len(secret) < 32:
        logging.warning("JWT_SECRET_KEY is shorter than the recommended 32 characters")
