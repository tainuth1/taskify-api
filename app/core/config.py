from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "Taskify"
    DESCRIBTION: str = "A simple task management system app"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    
    # PostgreSQL Database
    DATABASE_URL: Optional[str] = None

    # Front-End URL:
    FRONTEND_URL: str = "http://localhost:3000"
    
    # JWT
    SECRET_KEY: Optional[str] = None
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    # app/core/config.py
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Cookie config
    ACCESS_TOKEN_COOKIE_NAME: str = "access_token"
    REFRESH_TOKEN_COOKIE_NAME: str = "refresh_token"
    COOKIE_DOMAIN: str | None = ""
    COOKIE_SECURE: bool = False # false for local development
    COOKIE_SAMESITE: str = "lax" # "lax" or "none" (use "none" for cross-site)
    
    # Cloudinary
    CLOUDINARY_CLOUD_NAME: str
    CLOUDINARY_API_KEY: str
    CLOUDINARY_API_SECRET: str

    # Brevo Email sender
    BREVO_API_KEY: str
    BREVO_SENDER_EMAIL: str
    BREVO_SENDER_NAME: str = "Taskify"
    OTP_EXPIRE_MINUTES: int = 5
    RESET_PASSWORD_TOKEN_EXPIRE_MINUTES: int = 5

    # Rate Limiting Configuration
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60  # Default: 60 requests per minute
    RATE_LIMIT_PER_HOUR: int = 1000  # Default: 1000 requests per hour

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()