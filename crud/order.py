from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_, func, desc
from sqlalchemy.orm import selectinload, joinedload
from typing import Optional, List, Tuple
from datetime import datetime, timedelta
import random
import string

from models.models import Order, OrderItem, MenuItem
from schemas.schemas import OrderStatus
from core.config import settings
from core.security import generate_otp

async def create_order(
    db: AsyncSession,
    customer_id: int,
    service_id: int,
    address: str,
    phone: str,
    special_instructions: Optional[str],
    items: List[Tuple[int, int]]  # List of (menu_item_id, quantity)
) -> Optional[Order]:
    """Create new order"""
    
    # Calculate total amount and validate items
    total_amount = 0.0
    order_items = []
    
    for menu_item_id, quantity in items:
        # Get menu item
        result = await db.execute(
            select(MenuItem).where(
                and_(
                    MenuItem.id == menu_item_id,
                    MenuItem.is_available == True
                )
            )
        )
        menu_item = result.scalar_one_or_none()
        
        if not menu_item:
            return None
        
        # Add to total
        item_total = menu_item.price * quantity
        total_amount += item_total
        
        # Create order item
        order_item = OrderItem(
            menu_item_id=menu_item_id,
            quantity=quantity,
            price_at_order=menu_item.price
        )
        order_items.append(order_item)
    
    # Create order
    db_order = Order(
        customer_id=customer_id,
        service_id=service_id,
        total_amount=total_amount,
        address=address,
        phone=phone,
        special_instructions=special_instructions,
        order_items=order_items
    )
    
    db.add(db_order)
    await db.commit()
    await db.refresh(db_order)
    return db_order

async def get_order_by_id(db: AsyncSession, order_id: int) -> Optional[Order]:
    """Get order by ID with all relationships"""
    result = await db.execute(
        select(Order)
        .options(
            selectinload(Order.customer),
            selectinload(Order.service),
            selectinload(Order.assigned_to_user),
            selectinload(Order.order_items).joinedload(OrderItem.menu_item)
        )
        .where(Order.id == order_id)
    )
    return result.scalar_one_or_none()

async def get_order_by_number(db: AsyncSession, order_number: str) -> Optional[Order]:
    """Get order by order number"""
    result = await db.execute(
        select(Order).where(Order.order_number == order_number)
    )
    return result.scalar_one_or_none()

async def get_orders_by_customer(db: AsyncSession, customer_id: int, skip: int = 0, limit: int = 50) -> List[Order]:
    """Get all orders for a customer"""
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.service))
        .where(Order.customer_id == customer_id)
        .order_by(desc(Order.created_at))
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def get_orders_by_team_member(db: AsyncSession, team_member_id: int, skip: int = 0, limit: int = 50) -> List[Order]:
    """Get orders assigned to a team member"""
    result = await db.execute(
        select(Order)
        .options(
            selectinload(Order.customer),
            selectinload(Order.service),
            selectinload(Order.order_items).joinedload(OrderItem.menu_item)
        )
        .where(and_(
            Order.assigned_to == team_member_id,
            Order.status.in_([OrderStatus.CONFIRMED.value, OrderStatus.PREPARING.value, OrderStatus.OUT_FOR_DELIVERY.value])
        ))
        .order_by(Order.created_at)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def get_all_orders(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
) -> Tuple[List[Order], int]:
    """Get all orders with filters and total count"""
    
    # Build query
    query = select(Order).options(
        selectinload(Order.customer),
        selectinload(Order.service),
        selectinload(Order.assigned_to_user)
    )
    
    # Apply filters
    conditions = []
    if status:
        conditions.append(Order.status == status)
    if date_from:
        conditions.append(Order.created_at >= date_from)
    if date_to:
        conditions.append(Order.created_at <= date_to)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    # Get total count
    count_query = select(func.count(Order.id))
    if conditions:
        count_query = count_query.where(and_(*conditions))
    
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    # Get paginated results
    query = query.order_by(desc(Order.created_at)).offset(skip).limit(limit)
    result = await db.execute(query)
    orders = result.scalars().all()
    
    return orders, total

async def update_order_status(db: AsyncSession, order_id: int, status: OrderStatus) -> Optional[Order]:
    """Update order status"""
    await db.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(status=status.value, updated_at=datetime.utcnow())
    )
    await db.commit()
    return await get_order_by_id(db, order_id)

async def assign_order(db: AsyncSession, order_id: int, team_member_id: int) -> Optional[Order]:
    """Assign order to team member"""
    await db.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(
            assigned_to=team_member_id,
            status=OrderStatus.CONFIRMED.value,
            updated_at=datetime.utcnow()
        )
    )
    await db.commit()
    return await get_order_by_id(db, order_id)

async def generate_order_otp(db: AsyncSession, order_id: int) -> Optional[Tuple[str, datetime]]:
    """Generate OTP for order delivery"""
    order = await get_order_by_id(db, order_id)
    if not order:
        return None
    
    # Check if OTP attempts exceeded
    if order.otp_attempts >= settings.OTP_MAX_ATTEMPTS:
        return None
    
    # Generate new OTP
    otp = generate_otp()
    otp_expiry = datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)
    
    await db.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(
            otp=otp,
            otp_expiry=otp_expiry,
            otp_attempts=order.otp_attempts + 1,
            updated_at=datetime.utcnow()
        )
    )
    await db.commit()
    
    return otp, otp_expiry

async def verify_order_otp(db: AsyncSession, order_id: int, otp: str) -> bool:
    """Verify OTP for order delivery"""
    order = await get_order_by_id(db, order_id)
    if not order:
        return False
    
    # Check OTP attempts
    if order.otp_attempts >= settings.OTP_MAX_ATTEMPTS:
        return False
    
    # Check OTP expiry
    if not order.otp_expiry or datetime.utcnow() > order.otp_expiry:
        return False
    
    # Verify OTP
    if order.otp != otp:
        # Increment attempts
        await db.execute(
            update(Order)
            .where(Order.id == order_id)
            .values(otp_attempts=order.otp_attempts + 1)
        )
        await db.commit()
        return False
    
    # OTP verified, mark order as delivered
    await db.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(
            status=OrderStatus.DELIVERED.value,
            otp=None,
            otp_expiry=None,
            updated_at=datetime.utcnow()
        )
    )
    await db.commit()
    
    return True

async def get_order_statistics(
    db: AsyncSession,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
) -> dict:
    """Get order statistics"""
    
    # Base query
    query = select(
        func.count(Order.id).label('total_orders'),
        func.coalesce(func.sum(Order.total_amount), 0).label('total_revenue'),
        func.avg(Order.total_amount).label('avg_order_value')
    )
    
    # Apply date filters
    conditions = []
    if date_from:
        conditions.append(Order.created_at >= date_from)
    if date_to:
        conditions.append(Order.created_at <= date_to)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    result = await db.execute(query)
    stats = result.first()
    
    # Get status distribution
    status_query = select(
        Order.status,
        func.count(Order.id).label('count')
    ).group_by(Order.status)
    
    if conditions:
        status_query = status_query.where(and_(*conditions))
    
    status_result = await db.execute(status_query)
    status_dist = dict(status_result.all())
    
    return {
        'total_orders': stats.total_orders or 0,
        'total_revenue': float(stats.total_revenue or 0),
        'avg_order_value': float(stats.avg_order_value or 0),
        'status_distribution': status_dist
    }
