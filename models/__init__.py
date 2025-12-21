# models/__init__.py
"""
Models package initialization.
Exports all models and database components for easy access.
"""

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from pydantic_settings import BaseSettings
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database URL from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+asyncpg://user:password@localhost/dbname"
)

# Create async engine
engine = create_async_engine(DATABASE_URL, echo=True)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Base class for all models
class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass

# Dependency to get DB session
async def get_db() -> AsyncSession:
    """
    Dependency function to get database session.
    Usage in FastAPI endpoints:
        @app.get("/items")
        async def read_items(db: AsyncSession = Depends(get_db)):
            # use db session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# Import all models (they should inherit from Base)
# Note: Import models after Base is defined
from .models import *

# Optional: If you have multiple model files
# from .user_models import User, Profile
# from .product_models import Product, Category
# from .order_models import Order, OrderItem

# Export commonly used items
__all__ = [
    'Base',
    'engine',
    'AsyncSessionLocal',
    'get_db',
    'AsyncSession',
    # Add your model classes here
    # 'User',
    # 'Product',
    # 'Order',
]