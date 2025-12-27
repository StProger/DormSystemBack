from pydantic_settings import BaseSettings
from pydantic import AnyUrl
from functools import lru_cache

class Settings(BaseSettings):
    APP_NAME: str = "Dorm Management API"
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    DATABASE_URL: AnyUrl
    JWT_SECRET: str
    JWT_ALG: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # MinIO (S3)
    S3_ENDPOINT: str = "localhost:9000"     # host:port
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "dorm-files"
    S3_SECURE: bool = False                 # True если https

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache
def get_settings() -> Settings:
    return Settings()
