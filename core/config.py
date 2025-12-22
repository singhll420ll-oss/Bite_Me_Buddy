# File: config.py
import os
from typing import List
from pydantic import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Bite Me Buddy"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8000))
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://bite_me_buddy_user:6Mb7axQ89EkOQTQnqw6shT5CaO2lFY1Z@dpg-d536f8khg0os738kuhm0-a/bite_me_buddy"
    )
    
    # JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
    
    # File Upload
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_IMAGE_TYPES: List[str] = ["jpg", "jpeg", "png", "gif", "webp"]
    UPLOAD_DIR: str = "static/uploads"
    
    # Email
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", 587))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    FROM_EMAIL: str = os.getenv("FROM_EMAIL", "noreply@bitemebuddy.com")
    FROM_NAME: str = os.getenv("FROM_NAME", "Bite Me Buddy")
    
    # Site
    SITE_URL: str = os.getenv("SITE_URL", "http://localhost:8000")
    SITE_NAME: str = "Bite Me Buddy"
    
    # Payment (Example: Razorpay)
    RAZORPAY_KEY_ID: str = os.getenv("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET: str = os.getenv("RAZORPAY_KEY_SECRET", "")
    
    # SMS (Example: Twilio)
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE_NUMBER: str = os.getenv("TWILIO_PHONE_NUMBER", "")
    
    # Google Maps
    GOOGLE_MAPS_API_KEY: str = os.getenv("GOOGLE_MAPS_API_KEY", "")
    
    # Redis (for caching)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # Cache
    CACHE_TTL: int = 300  # 5 minutes
    
    # Security
    PASSWORD_RESET_TIMEOUT: int = 3600  # 1 hour
    OTP_EXPIRY_MINUTES: int = 10
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_TIME_MINUTES: int = 15
    
    # Business Logic
    TAX_RATE: float = 0.18  # 18% GST
    BASE_DELIVERY_CHARGE: float = 20.0
    FREE_DELIVERY_THRESHOLD: float = 500.0
    DEFAULT_PREPARATION_TIME: int = 30  # minutes
    
    # Order
    DEFAULT_DELIVERY_TIME: int = 45  # minutes
    ORDER_STATUS_UPDATE_DELAY: int = 5  # minutes between status updates
    
    # Commission
    COMMISSION_RATE: float = 0.10  # 10% commission on orders
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Create settings instance
settings = Settings()

# Export configuration
def get_settings() -> Settings:
    return settings
