from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
import ssl
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Your PostgreSQL URL
DATABASE_URL = "postgresql://bite_me_buddy_user:6Mb7axQ89EkOQTQnqw6shT5CaO2lFY1Z@dpg-d536f8khg0os738kuhm0-a/bite_me_buddy"

print(f"🔍 PostgreSQL Database URL detected")
print(f"📁 Database: bite_me_buddy")
print(f"👤 User: bite_me_buddy_user")

# ========== ASYNC DATABASE (For FastAPI endpoints) ==========

# Convert to asyncpg URL for PostgreSQL
async_database_url = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
print(f"✅ Using asyncpg driver for FastAPI")

# This is a Render PostgreSQL database
is_render_db = True
print("🌐 Render PostgreSQL database detected")

# Add SSL requirement for Render
if "?" not in async_database_url:
    async_database_url += "?ssl=require"
else:
    async_database_url += "&ssl=require"

# Configure SSL for Render
engine_kwargs = {
    "echo": True,  # Set to True for debugging SQL queries
    "poolclass": NullPool,
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "connect_args": {
        "ssl": ssl.create_default_context(),
        "server_settings": {"jit": "off"}
    }
}

print(f"🔧 Creating async PostgreSQL engine with SSL...")

# Create async engine
async_engine = create_async_engine(async_database_url, **engine_kwargs)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# ========== SYNC DATABASE (For authentication) ==========

# Use original PostgreSQL URL for sync operations (psycopg2)
sync_database_url = DATABASE_URL
print(f"🔧 Creating sync PostgreSQL engine for authentication...")

# Create sync engine with psycopg2
engine = create_engine(
    sync_database_url,
    echo=False,  # Set to False in production
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=5,
    max_overflow=10,
    connect_args={
        "sslmode": "require"
    }
)

# Create sync session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

# ========== DATABASE FUNCTIONS ==========

async def get_db():
    """Dependency to get async database session for FastAPI endpoints"""
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception as e:
        print(f"❌ Async database error: {e}")
        await session.rollback()
        raise
    finally:
        await session.close()

def get_sync_db():
    """Dependency to get sync database session (for mobile authentication)"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        print(f"❌ Sync database error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def get_db_sync():
    """Get sync database session directly"""
    return SessionLocal()

async def init_db():
    """Initialize database (create tables)"""
    try:
        print("🔄 Creating PostgreSQL tables for bite_me_buddy database...")
        
        # Import models
        from models.models import Base
        
        # Create tables using async engine
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        print("✅ PostgreSQL tables created successfully!")
        
        # Also ensure tables exist in sync engine
        Base.metadata.create_all(bind=engine)
        
        return True
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_connection():
    """Test PostgreSQL database connection"""
    try:
        # Test async connection
        async with AsyncSessionLocal() as session:
            result = await session.execute("SELECT version()")
            version = result.scalar()
            print(f"✅ PostgreSQL connected! Version: {version}")
            
            # Check current database
            result = await session.execute("SELECT current_database()")
            db_name = result.scalar()
            print(f"📊 Connected to database: {db_name}")
            
            # Check tables
            result = await session.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"
            )
            tables = result.scalars().all()
            print(f"📋 Found {len(tables)} tables: {tables}")
            
            # Check if users table exists
            if 'users' in tables:
                result = await session.execute("SELECT COUNT(*) FROM users")
                count = result.scalar()
                print(f"👥 Users table has {count} records")
            else:
                print("⚠️ Users table does not exist yet")
            
            return True
    except Exception as e:
        print(f"❌ Async PostgreSQL connection failed: {e}")
        
        # Try sync connection
        try:
            with SessionLocal() as session:
                result = session.execute("SELECT version()")
                version = result.scalar()
                print(f"✅ Sync PostgreSQL connected! Version: {version}")
                return True
        except Exception as e2:
            print(f"❌ Sync PostgreSQL connection also failed: {e2}")
            import traceback
            traceback.print_exc()
            return False

# ========== MOBILE AUTHENTICATION HELPERS ==========

def get_user_by_mobile_sync(mobile: str):
    """Get user by mobile number using sync session"""
    from models.models import User
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.mobile == mobile).first()
        return user
    finally:
        db.close()

def create_user_sync(mobile: str, hashed_password: str):
    """Create new user using sync session"""
    from models.models import User
    
    db = SessionLocal()
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.mobile == mobile).first()
        if existing_user:
            raise ValueError(f"User with mobile {mobile} already exists")
        
        # Create new user
        user = User(
            mobile=mobile,
            password=hashed_password,
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"✅ User created: {mobile}")
        return user
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating user: {e}")
        raise
    finally:
        db.close()

def verify_user_sync(mobile: str, password: str):
    """Verify user credentials"""
    from models.models import User
    from passlib.context import CryptContext
    
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.mobile == mobile).first()
        if not user:
            return None
        
        if not pwd_context.verify(password, user.password):
            return None
        
        return user
    finally:
        db.close()

# ========== DATABASE UTILITIES ==========

async def list_all_tables():
    """List all tables in the database"""
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute("""
                SELECT 
                    table_name,
                    (SELECT COUNT(*) FROM information_schema.columns 
                     WHERE table_schema = 'public' AND table_name = t.table_name) as column_count
                FROM information_schema.tables t
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            tables = result.fetchall()
            
            print("📊 Database Tables:")
            for table in tables:
                print(f"  - {table[0]} ({table[1]} columns)")
            
            return tables
    except Exception as e:
        print(f"❌ Error listing tables: {e}")
        return []

async def get_user_count():
    """Get total number of users"""
    try:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import text
            result = await session.execute(text("SELECT COUNT(*) FROM users"))
            count = result.scalar()
            return count or 0
    except:
        return 0

# ========== INITIALIZE ON IMPORT ==========

# Create a simple initialization check
print("🚀 Initializing database connection...")

# Run a quick test in background
import asyncio
import threading

def background_init():
    """Initialize database in background"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(test_connection())
        if success:
            print("🎉 Database connection established successfully!")
        else:
            print("⚠️  Database connection needs attention")
        loop.close()
    except:
        print("⚠️  Background initialization skipped")

# Start background initialization
thread = threading.Thread(target=background_init, daemon=True)
thread.start()