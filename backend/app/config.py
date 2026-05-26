from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # JWT
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Storage
    STORAGE_TYPE: str = "local"
    LOCAL_STORAGE_PATH: str = "/app/data/documents"

    # API
    ENVIRONMENT: str = "production"
    DEBUG: bool = False
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # CORS — default open so it works behind any reverse proxy
    CORS_ORIGINS: List[str] = ["*"]

    # Phase 2
    ANTHROPIC_API_KEY: str = ""
    ENABLE_OCR: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
