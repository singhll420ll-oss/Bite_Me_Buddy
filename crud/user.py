from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, func, or_
from sqlalchemy.orm import selectinload
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
import re

from models.models import User, Order, UserSession
from schemas.schemas import UserCreate, UserRole, UserLogin, UserProfileUpdate, PasswordChange
from core.security import get_password_hash, verify_password

# ========== MOBILE AUTHENTICATION FUNCTIONS ==========

def clean_mobile_number(mobile: str) -> str:
    """Clean mobile number by removing non-digit characters"""
    return re.sub(r'\D', '', mobile)

def validate_mobile_number(mobile: str) -> bool:
    """Validate mobile number format"""
    clean_mobile = clean_mobile_number(mobile)
    
    # Check if it's 10 digits
    if len(clean_mobile) != 10:
        return False
    
    # Check if it starts with valid Indian prefix
    if not clean_mobile.startswith(('6', '7', '8', '9')):
        return False
    
    return True

async def get_user_by_mobile(db: AsyncSession, mobile: str) -> Optional[User]:
    """Get user by mobile number"""
    clean_mobile = clean_mobile_number(mobile)
    
    result = await db.execute(
        select(User).where(User.mobile == clean_mobile)
    )
    return result.scalar_one_or_none()

async def create_user(db: AsyncSession, user_data: UserCreate) -> User:
    """Create new user with mobile authentication"""
    # Clean and validate mobile number
    clean_mobile = clean_mobile_number(user_data.mobile)
    
    if not validate_mobile_number(clean_mobile):
        raise ValueError("Invalid mobile number format")
    
    # Check if user already exists
    existing_user = await get_user_by_mobile(db, clean_mobile)
    if existing_user:
        raise ValueError(f"User with mobile {clean_mobile} already exists")
    
    # Check if email is provided and unique
    if user_data.email:
        existing_email_user = await get_user_by_email(db, user_data.email)
        if existing_email_user:
            raise ValueError(f"User with email {user_data.email} already exists")
    
    # Create user
    db_user = User(
        mobile=clean_mobile,
        name=user_data.name,
        email=user_data.email,
        address=user_data.address,
        role=user_data.role.value if hasattr(user_data.role, 'value') else user_data.role
    )
    
    # Set password using model method
    db_user.set_password(user_data.password)
    
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def authenticate_user(db: AsyncSession, mobile: str, password: str) -> Optional[User]:
    """Authenticate user with mobile and password"""
    user = await get_user_by_mobile(db, mobile)
    if not user:
        return None
    
    if not user.verify_password(password):
        return None
    
    if not user.is_active:
        return None
    
    return user

async def authenticate_user_with_email(db: AsyncSession, email: str, password: str) -> Optional[User]:
    """Authenticate user with email and password (backward compatibility)"""
    user = await get_user_by_email(db, email)
    if not user:
        return None
    
    if not user.verify_password(password):
        return None
    
    if not user.is_active:
        return None
    
    return user

# ========== EXISTING FUNCTIONS (UPDATED) ==========

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
    """Get user by phone (legacy field)"""
    result = await db.execute(
        select(User).where(User.phone == phone)
    )
    return result.scalar_one_or_none()

async def update_user(db: AsyncSession, user_id: int, update_data: dict) -> Optional[User]:
    """Update user information"""
    # Remove password from update_data if present
    update_data.pop('password', None)
    
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

async def get_customer_with_stats(db: AsyncSession, user_id: int) -> Optional[Dict[str, Any]]:
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

# ========== NEW MOBILE AUTH FUNCTIONS ==========

async def update_user_profile(db: AsyncSession, user_id: int, profile_data: UserProfileUpdate) -> Optional[User]:
    """Update user profile information"""
    user = await get_user_by_id(db, user_id)
    if not user:
        return None
    
    update_fields = {}
    
    if profile_data.name is not None:
        update_fields['name'] = profile_data.name
    if profile_data.email is not None:
        # Check if email is already taken by another user
        if profile_data.email:
            existing_user = await get_user_by_email(db, profile_data.email)
            if existing_user and existing_user.id != user_id:
                raise ValueError(f"Email {profile_data.email} is already registered")
        update_fields['email'] = profile_data.email
    if profile_data.address is not None:
        update_fields['address'] = profile_data.address
    
    if update_fields:
        update_fields['updated_at'] = datetime.utcnow()
        await update_user(db, user_id, update_fields)
    
    return await get_user_by_id(db, user_id)

async def change_user_password(db: AsyncSession, user_id: int, password_data: PasswordChange) -> bool:
    """Change user password"""
    user = await get_user_by_id(db, user_id)
    if not user:
        return False
    
    # Verify current password
    if not user.verify_password(password_data.current_password):
        return False
    
    # Set new password
    user.set_password(password_data.new_password)
    user.updated_at = datetime.utcnow()
    
    await db.commit()
    return True

async def update_user_mobile(db: AsyncSession, user_id: int, new_mobile: str, password: str) -> bool:
    """Update user's mobile number"""
    user = await get_user_by_id(db, user_id)
    if not user:
        return False
    
    # Verify password
    if not user.verify_password(password):
        return False
    
    # Clean and validate new mobile
    clean_mobile = clean_mobile_number(new_mobile)
    if not validate_mobile_number(clean_mobile):
        raise ValueError("Invalid mobile number format")
    
    # Check if new mobile is already taken
    existing_user = await get_user_by_mobile(db, clean_mobile)
    if existing_user and existing_user.id != user_id:
        raise ValueError(f"Mobile number {clean_mobile} is already registered")
    
    # Update mobile
    user.mobile = clean_mobile
    user.updated_at = datetime.utcnow()
    
    await db.commit()
    return True

async def search_users(db: AsyncSession, search_term: str, skip: int = 0, limit: int = 50) -> List[User]:
    """Search users by mobile, name, or email"""
    clean_search = search_term.strip()
    
    result = await db.execute(
        select(User)
        .where(
            and_(
                User.is_active == True,
                or_(
                    User.mobile.ilike(f"%{clean_search}%"),
                    User.name.ilike(f"%{clean_search}%"),
                    User.email.ilike(f"%{clean_search}%")
                )
            )
        )
        .order_by(User.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def get_user_stats(db: AsyncSession) -> Dict[str, Any]:
    """Get user statistics"""
    # Total users
    total_result = await db.execute(
        select(func.count(User.id)).where(User.is_active == True)
    )
    total_users = total_result.scalar() or 0
    
    # Users by role
    role_result = await db.execute(
        select(User.role, func.count(User.id).label('count'))
        .where(User.is_active == True)
        .group_by(User.role)
    )
    users_by_role = {row[0]: row[1] for row in role_result.all()}
    
    # New users today
    today = date.today()
    new_today_result = await db.execute(
        select(func.count(User.id))
        .where(
            and_(
                User.is_active == True,
                func.date(User.created_at) == today
            )
        )
    )
    new_today = new_today_result.scalar() or 0
    
    return {
        "total_users": total_users,
        "users_by_role": users_by_role,
        "new_users_today": new_today
    }

async def create_user_session(db: AsyncSession, user_id: int, ip_address: str = None, user_agent: str = None) -> UserSession:
    """Create a new user session record"""
    session = UserSession(
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session

async def update_user_session_logout(db: AsyncSession, session_id: int) -> Optional[UserSession]:
    """Update session logout time"""
    result = await db.execute(
        select(UserSession).where(UserSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    
    if session:
        session.logout_time = datetime.utcnow()
        await db.commit()
        await db.refresh(session)
    
    return session