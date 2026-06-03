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
