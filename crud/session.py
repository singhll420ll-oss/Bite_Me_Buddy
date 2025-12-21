from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, func, or_
from sqlalchemy.orm import selectinload
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime, date, timedelta

from models.models import UserSession, User

# ========== SESSION MANAGEMENT ==========

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

async def update_session_logout_by_user(db: AsyncSession, user_id: int) -> bool:
    """Update all active sessions for a user to logout"""
    await db.execute(
        update(UserSession)
        .where(and_(
            UserSession.user_id == user_id,
            UserSession.logout_time.is_(None)
        ))
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

async def get_user_sessions_by_mobile(
    db: AsyncSession,
    mobile: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    skip: int = 0,
    limit: int = 100
) -> Tuple[List[UserSession], int]:
    """Get user sessions by mobile number"""
    # First get user by mobile
    from crud.user import get_user_by_mobile
    user = await get_user_by_mobile(db, mobile)
    
    if not user:
        return [], 0
    
    # Then get their sessions
    return await get_user_sessions(db, user.id, date_from, date_to, skip, limit)

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

# ========== STATISTICS AND REPORTS ==========

async def get_online_time_report(
    db: AsyncSession,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None
) -> List[Dict[str, Any]]:
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
    
    # Join with users - UPDATED for mobile field
    query = select(
        User.id,
        User.mobile,  # ✅ Use mobile instead of username
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
        User.mobile,  # ✅ Group by mobile
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
            'mobile': row.mobile,  # ✅ Return mobile
            'name': row.name,
            'role': row.role,
            'total_sessions': row.session_count,
            'total_time_minutes': round(row.total_minutes or 0, 2),
            'avg_session_minutes': round(avg_session, 2),
            'last_login': row.last_login
        })
    
    return report

async def get_user_online_stats(
    db: AsyncSession,
    user_id: int
) -> Dict[str, Any]:
    """Get online statistics for a specific user"""
    
    # Total sessions
    total_sessions_query = select(
        func.count(UserSession.id).label('total_sessions'),
        func.sum(
            func.extract('epoch', UserSession.logout_time - UserSession.login_time) / 60
        ).label('total_minutes')
    ).where(and_(
        UserSession.user_id == user_id,
        UserSession.logout_time.is_not(None)
    ))
    
    total_result = await db.execute(total_sessions_query)
    total_stats = total_result.first()
    
    # Current month sessions
    today = datetime.utcnow()
    month_start = today.replace(day=1)
    
    month_sessions_query = select(
        func.count(UserSession.id).label('month_sessions'),
        func.sum(
            func.extract('epoch', UserSession.logout_time - UserSession.login_time) / 60
        ).label('month_minutes')
    ).where(and_(
        UserSession.user_id == user_id,
        UserSession.logout_time.is_not(None),
        UserSession.login_time >= month_start
    ))
    
    month_result = await db.execute(month_sessions_query)
    month_stats = month_result.first()
    
    # Last login
    last_login_query = select(
        UserSession.login_time
    ).where(
        UserSession.user_id == user_id
    ).order_by(
        UserSession.login_time.desc()
    ).limit(1)
    
    last_login_result = await db.execute(last_login_query)
    last_login_row = last_login_result.first()
    
    return {
        'total_sessions': total_stats.total_sessions or 0,
        'total_minutes': round(total_stats.total_minutes or 0, 2),
        'month_sessions': month_stats.month_sessions or 0,
        'month_minutes': round(month_stats.month_minutes or 0, 2),
        'last_login': last_login_row[0] if last_login_row else None,
        'avg_session_minutes': round(
            (total_stats.total_minutes or 0) / (total_stats.total_sessions or 1), 2
        )
    }

async def get_active_sessions(db: AsyncSession) -> List[UserSession]:
    """Get all active sessions (not logged out)"""
    result = await db.execute(
        select(UserSession)
        .options(selectinload(UserSession.user))
        .where(UserSession.logout_time.is_(None))
        .order_by(UserSession.login_time.desc())
    )
    return result.scalars().all()

async def get_active_sessions_count(db: AsyncSession) -> int:
    """Get count of active sessions"""
    result = await db.execute(
        select(func.count(UserSession.id))
        .where(UserSession.logout_time.is_(None))
    )
    return result.scalar() or 0

# ========== DASHBOARD STATISTICS ==========

async def get_daily_sessions_stats(
    db: AsyncSession,
    days: int = 30
) -> List[Dict[str, Any]]:
    """Get daily session statistics for last N days"""
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    query = select(
        UserSession.date,
        func.count(UserSession.id).label('session_count'),
        func.count(func.distinct(UserSession.user_id)).label('unique_users')
    ).where(
        UserSession.date.between(start_date, end_date)
    ).group_by(
        UserSession.date
    ).order_by(
        UserSession.date.desc()
    )
    
    result = await db.execute(query)
    rows = result.all()
    
    stats = []
    for row in rows:
        stats.append({
            'date': row.date,
            'session_count': row.session_count,
            'unique_users': row.unique_users
        })
    
    return stats

async def get_user_activity_timeline(
    db: AsyncSession,
    user_id: int,
    days: int = 7
) -> List[Dict[str, Any]]:
    """Get user activity timeline for last N days"""
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    query = select(
        UserSession.date,
        func.count(UserSession.id).label('daily_sessions'),
        func.sum(
            func.extract('epoch', UserSession.logout_time - UserSession.login_time) / 60
        ).label('daily_minutes')
    ).where(and_(
        UserSession.user_id == user_id,
        UserSession.date.between(start_date, end_date),
        UserSession.logout_time.is_not(None)
    )).group_by(
        UserSession.date
    ).order_by(
        UserSession.date.desc()
    )
    
    result = await db.execute(query)
    rows = result.all()
    
    timeline = []
    for row in rows:
        timeline.append({
            'date': row.date,
            'daily_sessions': row.daily_sessions,
            'daily_minutes': round(row.daily_minutes or 0, 2)
        })
    
    return timeline

async def get_peak_usage_hours(db: AsyncSession, days: int = 7) -> List[Dict[str, Any]]:
    """Get peak usage hours for last N days"""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    query = select(
        func.extract('hour', UserSession.login_time).label('hour'),
        func.count(UserSession.id).label('session_count')
    ).where(
        UserSession.login_time.between(start_date, end_date)
    ).group_by(
        func.extract('hour', UserSession.login_time)
    ).order_by(
        func.count(UserSession.id).desc()
    ).limit(6)
    
    result = await db.execute(query)
    rows = result.all()
    
    peak_hours = []
    for row in rows:
        peak_hours.append({
            'hour': int(row.hour),
            'session_count': row.session_count,
            'hour_display': f"{int(row.hour):02d}:00"
        })
    
    return peak_hours