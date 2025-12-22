
# File: database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://bite_me_buddy_user:6Mb7axQ89EkOQTQnqw6shT5CaO2lFY1Z@dpg-d536f8khg0os738kuhm0-a/bite_me_buddy")

# Create engine
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False  # Set to True for SQL logging
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

def get_db():
    """
    Dependency to get DB session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """
    Initialize database (create tables)
    """
    from models import Base
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully")

def drop_db():
    """
    Drop all tables (for development/testing)
    """
    from models import Base
    Base.metadata.drop_all(bind=engine)
    print("⚠️  All tables dropped")
