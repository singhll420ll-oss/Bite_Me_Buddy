from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
import ssl

from core.config import settings

# Get DATABASE_URL from config
DATABASE_URL = settings.DATABASE_URL

print(f"🔍 DATABASE_URL from config: {DATABASE_URL[:50]}...")

# FIX 1: Ensure asyncpg driver for Render
if DATABASE_URL.startswith("postgresql://"):
    # Replace with asyncpg driver
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    print(f"✅ Converted to asyncpg URL")

# FIX 2: Add SSL for Render (if using Render's PostgreSQL)
# Check if it's a Render database
is_render_db = any(domain in DATABASE_URL for domain in ['render.com', 'dpg-', 'oregon-postgres.render.com'])

if is_render_db:
    print("🌐 Detected Render PostgreSQL - enabling SSL")
    # Ensure SSL parameters are in URL
    if "?" not in DATABASE_URL:
        DATABASE_URL += "?ssl=require"
    elif "ssl=require" not in DATABASE_URL:
        DATABASE_URL += "&ssl=require"

# FIX 3: Create engine with proper SSL context for Render
engine_kwargs = {
    "echo": True,  # Set to True for debugging, False in production
    "poolclass": NullPool,  # Better for serverless environments
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

# Add SSL context for Render
if is_render_db:
    # Create SSL context
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    engine_kwargs["connect_args"] = {
        "ssl": ssl_context,
        "server_settings": {
            "jit": "off"  # Turn off JIT for better performance
        }
    }

print(f"🔧 Creating engine with: {DATABASE_URL[:60]}...")

# Create async engine
engine = create_async_engine(DATABASE_URL, **engine_kwargs)

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
    """Dependency to get database session - FIXED VERSION"""
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception as e:
        print(f"❌ Database error: {e}")
        await session.rollback()
        raise
    finally:
        await session.close()

async def init_db():
    """Initialize database (create tables)"""
    try:
        print("🔄 Creating database tables...")
        
        # Import models here to avoid circular imports
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        from models.models import User, Service, MenuItem, Order, OrderItem, TeamMemberPlan, UserSession
        
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        print("✅ Database tables created successfully!")
        return True
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_connection():
    """Test database connection"""
    try:
        async with AsyncSessionLocal() as session:
            # Simple test query
            result = await session.execute("SELECT version()")
            version = result.scalar()
            print(f"✅ Database connected! PostgreSQL version: {version}")
            
            # Also check if our tables exist
            result = await session.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            )
            tables = result.scalars().all()
            print(f"📊 Found tables: {tables}")
            
            return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False