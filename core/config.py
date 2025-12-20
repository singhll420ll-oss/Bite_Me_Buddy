# core/config.py
from pydantic_settings import BaseSettings
from typing import Optional, List
import os
from pathlib import Path

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # ===== DATABASE CONFIGURATION =====
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://bite_me_buddy_user:6Mb7axQ89EkOQTQnqw6shT5CaO2lFY1Z@dpg-d536f8khg0os738kuhm0-a.oregon-postgres.render.com/bite_me_buddy"
    )
    
    # ===== SECURITY CONFIGURATION =====
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY", 
        "your-super-secret-key-minimum-32-characters-change-this-in-production-123"
    )
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    
    # ===== TWILIO (SMS) CONFIGURATION =====
    TWILIO_ACCOUNT_SID: Optional[str] = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN: Optional[str] = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_PHONE_NUMBER: Optional[str] = os.getenv("TWILIO_PHONE_NUMBER")
    
    # ===== APPLICATION SETTINGS =====
    APP_NAME: str = os.getenv("APP_NAME", "Bite Me Buddy")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")  # development, staging, production
    
    # ===== CORS SETTINGS =====
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "https://bite-me-buddy.onrender.com",
        "https://*.onrender.com",
        "*"  # For development only
    ]
    
    # ===== FILE UPLOAD CONFIGURATION =====
    UPLOAD_DIR: str = os.path.join(BASE_DIR, "static", "uploads")
    MAX_FILE_SIZE: int = 5 * 1024 * 1024  # 5MB
    ALLOWED_IMAGE_TYPES: List[str] = [
        "image/jpeg",
        "image/png", 
        "image/gif",
        "image/webp",
        "image/svg+xml"
    ]
    
    # ===== OTP & VERIFICATION =====
    OTP_EXPIRE_MINUTES: int = int(os.getenv("OTP_EXPIRE_MINUTES", "10"))
    OTP_MAX_ATTEMPTS: int = int(os.getenv("OTP_MAX_ATTEMPTS", "3"))
    ENABLE_OTP: bool = os.getenv("ENABLE_OTP", "False").lower() == "true"
    
    # ===== PASSWORD POLICY =====
    MIN_PASSWORD_LENGTH: int = 8
    REQUIRE_SPECIAL_CHAR: bool = True
    REQUIRE_UPPERCASE: bool = True
    REQUIRE_NUMBER: bool = True
    
    # ===== RENDER SPECIFIC =====
    PORT: int = int(os.getenv("PORT", "8000"))
    RENDER: bool = os.getenv("RENDER", "False").lower() == "true"
    
    # ===== LOGGING =====
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.path.join(BASE_DIR, "logs", "app.log")
    
    # ===== RATE LIMITING =====
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    
    # ===== SESSION CONFIG =====
    SESSION_TIMEOUT_MINUTES: int = 30
    COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "False").lower() == "true"
    
    # ===== EMAIL CONFIG (Future) =====
    SMTP_HOST: Optional[str] = os.getenv("SMTP_HOST")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: Optional[str] = os.getenv("SMTP_USER")
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD")
    EMAIL_FROM: Optional[str] = os.getenv("EMAIL_FROM")
    
    # ===== PAYMENT GATEWAY (Future) =====
    STRIPE_SECRET_KEY: Optional[str] = os.getenv("STRIPE_SECRET_KEY")
    STRIPE_PUBLISHABLE_KEY: Optional[str] = os.getenv("STRIPE_PUBLISHABLE_KEY")
    RAZORPAY_KEY_ID: Optional[str] = os.getenv("RAZORPAY_KEY_ID")
    RAZORPAY_KEY_SECRET: Optional[str] = os.getenv("RAZORPAY_KEY_SECRET")

    # ===== MODEL VALIDATION CONFIG =====
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
        @classmethod
        def customise_sources(cls, init_settings, env_settings, file_secret_settings):
            # Priority: env_settings > init_settings > file_secret_settings
            return env_settings, init_settings, file_secret_settings


# Create settings instance
settings = Settings()

# Post-initialization setup
def setup_environment():
    """Setup environment after settings are loaded"""
    
    # Create upload directory if it doesn't exist
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    
    # Create logs directory
    logs_dir = os.path.join(BASE_DIR, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    
    # Print configuration in debug mode
    if settings.DEBUG:
        print("=" * 50)
        print(f"🚀 {settings.APP_NAME} Configuration")
        print("=" * 50)
        print(f"Environment: {settings.ENVIRONMENT}")
        print(f"Debug Mode: {settings.DEBUG}")
        print(f"Database URL: {settings.DATABASE_URL[:50]}...")
        print(f"CORS Origins: {settings.CORS_ORIGINS}")
        print(f"Upload Directory: {settings.UPLOAD_DIR}")
        print(f"Running on Render: {settings.RENDER}")
        print("=" * 50)

# Run setup
setup_environment()