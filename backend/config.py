# backend/config.py
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # JWT
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # TMDB
    TMDB_API_KEY: str
    TMDB_BASE_URL: str = "https://api.themoviedb.org/3"
    TMDB_IMAGE_BASE: str = "https://image.tmdb.org/t/p/w500"

    # App
    APP_ENV: str = "production" # "development" or "production"
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # Backend public URL — used to build absolute stream URLs
    # In dev this is empty so the frontend uses relative /proxy/hls paths via Vite proxy
    # In prod set this to your deployed API URL e.g. https://your-api.onrender.com
    BACKEND_URL: str = ""

    # Cloudflare Worker proxy (optional)
    CF_WORKER_URL: Optional[str] = None

    class Config:
        env_file = ".env"

settings = Settings()