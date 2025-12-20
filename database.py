from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
import os
from urllib.parse import urlparse

from core.config import settings

# Get DATABASE_URL from settings
DATABASE_URL = settings.DATABASE_URL

print(f"🔍 Original DATABASE_URL: {DATABASE_URL}")

# FIX 1: Convert PostgreSQL URL for asyncpg (Render requirement)
if DATABASE_URL.startswith("postgresql://"):
    # Render requires postgresql+asyncpg:// for async
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    print(f"🔧 Converted to: {DATABASE_URL}")

# FIX 2: Add SSL mode for Render PostgreSQL
if "render.com" in DATABASE_URL or "postgresql+asyncpg://" in DATABASE_URL:
    # Add SSL parameters for Render
    if "?" not in DATABASE_URL:
        DATABASE_URL += "?ssl=require"
    elif "ssl=" not in DATABASE_URL:
        DATABASE_URL += "&ssl=require"
    
    print(f"🔐 SSL enabled: {DATABASE_URL}")

# Create async engine with Render-specific settings
engine = create_async_engine(
    DATABASE_URL,
    echo=settings.DEBUG,  # Set to True temporarily for debugging
    poolclass=NullPool,  # Better for serverless/Render
    connect_args={
        "ssl": "require" if "render.com" in DATABASE_URL else None
    }
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

Base = declarative_base()

async def get_db():
    """Dependency to get database session - FIXED"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            print(f"❌ Database session error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_db():
    """Initialize database (create tables)"""
    try:
        print("🔄 Creating database tables...")
        async with engine.begin() as conn:
            # Import models
            from models.models import User, Service, MenuItem, Order, OrderItem, TeamMemberPlan, UserSession
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Database tables created successfully!")
        return True
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False

async def test_connection():
    """Test database connection"""
    try:
        async with AsyncSessionLocal() as session:
            # Simple test query
            result = await session.execute("SELECT version()")
            version = result.scalar()
            print(f"✅ Database connected! PostgreSQL version: {version}")
            return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False