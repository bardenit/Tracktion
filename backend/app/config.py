from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    JWT_SECRET_KEY: str = "change-me-in-production"
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


settings = Settings()


def validate_production_secret(config: Settings) -> None:
    secret = config.JWT_SECRET_KEY.strip()
    if not config.DEBUG and (secret == "change-me-in-production" or len(secret) < 32):
        raise RuntimeError("JWT_SECRET_KEY must be a non-default secret of at least 32 characters in production")
