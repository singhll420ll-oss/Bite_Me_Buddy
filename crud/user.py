from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, func
from sqlalchemy.orm import selectinload
from typing import Optional, List
from datetime import datetime, date, timedelta

from models.models import User, Order, UserSession
from schemas.schemas import UserCreate, UserRole
from core.security import get_password_hash

async def create_user(db: AsyncSession, user_data: UserCreate) -> User:
    """Create new user"""
    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        name=user_data.name,
        username=user_data.username,
        email=user_data.email,
        phone=user_data.phone,
        address=user_data.address,
        hashed_password=hashed_password,
        role=user_data.role.value
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """Get user by username"""
    result = await db.execute(
        select(User).where(User.username == username)
    )
    return result.scalar_one_or_none()

async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """Get user by ID"""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalar_one_or_none()

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Get user by email"""
    result = await db.execute(
        select(User).where(User.email == email)
    )
    return result.scalar_one_or_none()

async def get_user_by_phone(db: AsyncSession, phone: str) -> Optional[User]:
    """Get user by phone"""
    result = await db.execute(
        select(User).where(User.phone == phone)
    )
    return result.scalar_one_or_none()

async def update_user(db: AsyncSession, user_id: int, update_data: dict) -> Optional[User]:
    """Update user information"""
    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(**update_data)
    )
    await db.commit()
    return await get_user_by_id(db, user_id)

async def delete_user(db: AsyncSession, user_id: int) -> bool:
    """Delete user (soft delete)"""
    user = await get_user_by_id(db, user_id)
    if user:
        user.is_active = False
        await db.commit()
        return True
    return False

async def get_all_users(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[User]:
    """Get all users with pagination"""
    result = await db.execute(
        select(User)
        .where(User.is_active == True)
        .order_by(User.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def get_users_by_role(db: AsyncSession, role: UserRole, skip: int = 0, limit: int = 100) -> List[User]:
    """Get users by role"""
    result = await db.execute(
        select(User)
        .where(and_(User.role == role.value, User.is_active == True))
        .order_by(User.name)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def get_customer_with_stats(db: AsyncSession, user_id: int):
    """Get customer with order statistics"""
    # Get user
    user_result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = user_result.scalar_one_or_none()
    
    if not user:
        return None
    
    # Get order stats
    orders_result = await db.execute(
        select(
            func.count(Order.id).label('total_orders'),
            func.coalesce(func.sum(Order.total_amount), 0).label('total_spent'),
            func.max(Order.created_at).label('last_order_date')
        )
        .where(Order.customer_id == user_id)
    )
    stats = orders_result.first()
    
    return {
        "user": user,
        "total_orders": stats.total_orders or 0,
        "total_spent": float(stats.total_spent or 0),
        "last_order_date": stats.last_order_date
  }
