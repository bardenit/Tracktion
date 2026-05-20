from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://vehicle_user:vehicle_password@postgres:5432/vehicle_tracker"
    DATABASE_HOST: str = "postgres"
    DATABASE_PORT: int = 5432
    DATABASE_NAME: str = "vehicle_tracker"
    DATABASE_USER: str = "vehicle_user"
    DATABASE_PASSWORD: str = "vehicle_password"

    # JWT
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Storage
    STORAGE_TYPE: str = "local"  # local, s3, b2, minio
    LOCAL_STORAGE_PATH: str = "/data/documents"

    # AWS S3
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    AWS_BUCKET_NAME: str = "vehicle-tracker-docs"

    # Backblaze B2
    B2_APP_KEY_ID: str = ""
    B2_APP_KEY: str = ""
    B2_BUCKET_ID: str = ""

    # MinIO
    MINIO_ENDPOINT: str = "http://minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET_NAME: str = "vehicle-tracker"

    # API
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Claude API (for Phase 2 OCR)
    ANTHROPIC_API_KEY: str = ""

    # Feature Flags
    ENABLE_OCR: bool = False
    ENABLE_PLATE_LOOKUP: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
