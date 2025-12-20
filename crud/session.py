from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, func
from sqlalchemy.orm import selectinload
from typing import Optional, List, Tuple
from datetime import datetime, date, timedelta

from models.models import UserSession, User

async def create_user_session(
    db: AsyncSession,
    user_id: int,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> UserSession:
    """Create new user session"""
    db_session = UserSession(
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent
    )
    db.add(db_session)
    await db.commit()
    await db.refresh(db_session)
    return db_session

async def update_user_session_logout(db: AsyncSession, session_id: int) -> bool:
    """Update session logout time"""
    await db.execute(
        update(UserSession)
        .where(UserSession.id == session_id)
        .values(logout_time=datetime.utcnow())
    )
    await db.commit()
    return True

async def get_user_sessions(
    db: AsyncSession,
    user_id: int,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    skip: int = 0,
    limit: int = 100
) -> Tuple[List[UserSession], int]:
    """Get user sessions with pagination"""
    
    # Build query
    query = select(UserSession).where(UserSession.user_id == user_id)
    
    # Apply date filters
    conditions = [UserSession.user_id == user_id]
    if date_from:
        conditions.append(UserSession.date >= date_from)
    if date_to:
        conditions.append(UserSession.date <= date_to)
    
    query = query.where(and_(*conditions))
    
    # Get total count
    count_query = select(func.count(UserSession.id)).where(and_(*conditions))
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    # Get paginated results
    result = await db.execute(
        query.order_by(UserSession.login_time.desc())
        .offset(skip)
        .limit(limit)
    )
    sessions = result.scalars().all()
    
    return sessions, total

async def get_all_user_sessions(
    db: AsyncSession,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    skip: int = 0,
    limit: int = 100
) -> Tuple[List[UserSession], int]:
    """Get all user sessions with pagination"""
    
    # Build query
    query = select(UserSession).options(selectinload(UserSession.user))
    
    # Apply date filters
    conditions = []
    if date_from:
        conditions.append(UserSession.date >= date_from)
    if date_to:
        conditions.append(UserSession.date <= date_to)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    # Get total count
    count_query = select(func.count(UserSession.id))
    if conditions:
        count_query = count_query.where(and_(*conditions))
    
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    # Get paginated results
    result = await db.execute(
        query.order_by(UserSession.login_time.desc())
        .offset(skip)
        .limit(limit)
    )
    sessions = result.scalars().all()
    
    return sessions, total

async def get_online_time_report(
    db: AsyncSession,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None
) -> List[dict]:
    """Get online time report for all users"""
    
    # Build base query
    subquery = select(
        UserSession.user_id,
        func.count(UserSession.id).label('session_count'),
        func.sum(
            func.extract('epoch', UserSession.logout_time - UserSession.login_time) / 60
        ).label('total_minutes')
    ).group_by(UserSession.user_id)
    
    # Apply date filters
    if date_from or date_to:
        conditions = []
        if date_from:
            conditions.append(UserSession.date >= date_from)
        if date_to:
            conditions.append(UserSession.date <= date_to)
        if conditions:
            subquery = subquery.where(and_(*conditions))
    
    # Get sessions with logout time only
    subquery = subquery.where(UserSession.logout_time.is_not(None))
    
    # Join with users
    query = select(
        User.id,
        User.username,
        User.name,
        User.role,
        subquery.c.session_count,
        subquery.c.total_minutes,
        func.max(UserSession.login_time).label('last_login')
    ).join(
        subquery, User.id == subquery.c.user_id
    ).outerjoin(
        UserSession, and_(
            User.id == UserSession.user_id,
            UserSession.logout_time.is_not(None)
        )
    ).group_by(
        User.id,
        User.username,
        User.name,
        User.role,
        subquery.c.session_count,
        subquery.c.total_minutes
    )
    
    result = await db.execute(query)
    rows = result.all()
    
    report = []
    for row in rows:
        avg_session = row.total_minutes / row.session_count if row.session_count > 0 else 0
        report.append({
            'user_id': row.id,
            'username': row.username,
            'name': row.name,
            'role': row.role,
            'total_sessions': row.session_count,
            'total_time_minutes': round(row.total_minutes or 0, 2),
            'avg_session_minutes': round(avg_session, 2),
            'last_login': row.last_login
        })
    
    return report

async def get_active_sessions(db: AsyncSession) -> List[UserSession]:
    """Get all active sessions (not logged out)"""
    result = await db.execute(
        select(UserSession)
        .options(selectinload(UserSession.user))
        .where(UserSession.logout_time.is_(None))
        .order_by(UserSession.login_time.desc())
    )
    return result.scalars().all()
