from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_, func, desc
from sqlalchemy.orm import selectinload, joinedload
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime, timedelta
import random
import string

from models.models import Order, OrderItem, MenuItem, User
from schemas.schemas import OrderStatus, OrderCreate, OrderItemCreate
from core.config import settings
from core.security import generate_otp

# ========== ORDER CREATION ==========

async def create_order_from_schema(
    db: AsyncSession,
    customer_id: int,
    order_data: OrderCreate
) -> Optional[Order]:
    """Create new order from OrderCreate schema"""
    # Calculate total amount and validate items
    total_amount = 0.0
    order_items = []
    
    for item_data in order_data.items:
        # Get menu item
        result = await db.execute(
            select(MenuItem).where(
                and_(
                    MenuItem.id == item_data.menu_item_id,
                    MenuItem.is_available == True
                )
            )
        )
        menu_item = result.scalar_one_or_none()
        
        if not menu_item:
            raise ValueError(f"Menu item {item_data.menu_item_id} not found or unavailable")
        
        # Add to total
        item_total = menu_item.price * item_data.quantity
        total_amount += item_total
        
        # Create order item
        order_item = OrderItem(
            menu_item_id=item_data.menu_item_id,
            quantity=item_data.quantity,
            price_at_order=menu_item.price
        )
        order_items.append(order_item)
    
    # Get customer to get mobile number
    customer_result = await db.execute(
        select(User).where(User.id == customer_id)
    )
    customer = customer_result.scalar_one_or_none()
    
    if not customer:
        raise ValueError(f"Customer {customer_id} not found")
    
    # Create order
    db_order = Order(
        customer_id=customer_id,
        service_id=order_data.service_id,
        total_amount=total_amount,
        address=order_data.address,
        phone=customer.mobile,  # Use customer's mobile number
        special_instructions=order_data.special_instructions,
        order_items=order_items
    )
    
    db.add(db_order)
    await db.commit()
    await db.refresh(db_order)
    return db_order

async def create_order(
    db: AsyncSession,
    customer_id: int,
    service_id: int,
    address: str,
    phone: str,
    special_instructions: Optional[str],
    items: List[Tuple[int, int]]  # List of (menu_item_id, quantity)
) -> Optional[Order]:
    """Create new order (legacy function)"""
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

# ========== ORDER RETRIEVAL ==========

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
        select(Order)
        .options(
            selectinload(Order.customer),
            selectinload(Order.service),
            selectinload(Order.order_items).joinedload(OrderItem.menu_item)
        )
        .where(Order.order_number == order_number)
    )
    return result.scalar_one_or_none()

async def get_orders_by_customer(db: AsyncSession, customer_id: int, skip: int = 0, limit: int = 50) -> List[Order]:
    """Get all orders for a customer"""
    result = await db.execute(
        select(Order)
        .options(
            selectinload(Order.service),
            selectinload(Order.order_items).joinedload(OrderItem.menu_item)
        )
        .where(Order.customer_id == customer_id)
        .order_by(desc(Order.created_at))
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def get_orders_by_customer_mobile(db: AsyncSession, mobile: str, skip: int = 0, limit: int = 50) -> List[Order]:
    """Get orders by customer mobile number"""
    # First get user by mobile
    from crud.user import get_user_by_mobile
    user = await get_user_by_mobile(db, mobile)
    
    if not user:
        return []
    
    # Then get their orders
    return await get_orders_by_customer(db, user.id, skip, limit)

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
    date_to: Optional[datetime] = None,
    customer_mobile: Optional[str] = None
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
    
    # Filter by customer mobile if provided
    if customer_mobile:
        # Get user by mobile
        from crud.user import get_user_by_mobile
        user = await get_user_by_mobile(db, customer_mobile)
        if user:
            conditions.append(Order.customer_id == user.id)
        else:
            # Return empty if user not found
            return [], 0
    
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

# ========== ORDER UPDATES ==========

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

async def update_order_delivery_address(
    db: AsyncSession,
    order_id: int,
    new_address: str
) -> Optional[Order]:
    """Update order delivery address"""
    await db.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(
            address=new_address,
            updated_at=datetime.utcnow()
        )
    )
    await db.commit()
    return await get_order_by_id(db, order_id)

async def cancel_order(db: AsyncSession, order_id: int) -> Optional[Order]:
    """Cancel an order"""
    order = await get_order_by_id(db, order_id)
    if not order:
        return None
    
    # Only pending orders can be cancelled
    if order.status != OrderStatus.PENDING.value:
        return None
    
    await update_order_status(db, order_id, OrderStatus.CANCELLED)
    return await get_order_by_id(db, order_id)

# ========== OTP MANAGEMENT ==========

async def generate_order_otp(db: AsyncSession, order_id: int) -> Optional[Tuple[str, datetime]]:
    """Generate OTP for order delivery"""
    order = await get_order_by_id(db, order_id)
    if not order:
        return None
    
    # Check if OTP attempts exceeded
    if hasattr(settings, 'OTP_MAX_ATTEMPTS'):
        if order.otp_attempts >= settings.OTP_MAX_ATTEMPTS:
            return None
    
    # Generate new OTP
    otp = generate_otp() if hasattr(generate_otp, '__call__') else str(random.randint(1000, 9999))
    
    otp_expiry_minutes = getattr(settings, 'OTP_EXPIRE_MINUTES', 10)
    otp_expiry = datetime.utcnow() + timedelta(minutes=otp_expiry_minutes)
    
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
    if hasattr(settings, 'OTP_MAX_ATTEMPTS'):
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

# ========== STATISTICS AND REPORTS ==========

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

async def get_customer_order_statistics(
    db: AsyncSession,
    customer_id: int
) -> Dict[str, Any]:
    """Get order statistics for a specific customer"""
    
    # Total orders and revenue
    query = select(
        func.count(Order.id).label('total_orders'),
        func.coalesce(func.sum(Order.total_amount), 0).label('total_spent'),
        func.avg(Order.total_amount).label('avg_order_value'),
        func.max(Order.created_at).label('last_order_date')
    ).where(Order.customer_id == customer_id)
    
    result = await db.execute(query)
    stats = result.first()
    
    # Order status breakdown
    status_query = select(
        Order.status,
        func.count(Order.id).label('count')
    ).where(Order.customer_id == customer_id).group_by(Order.status)
    
    status_result = await db.execute(status_query)
    status_breakdown = dict(status_result.all())
    
    return {
        'total_orders': stats.total_orders or 0,
        'total_spent': float(stats.total_spent or 0),
        'avg_order_value': float(stats.avg_order_value or 0),
        'last_order_date': stats.last_order_date,
        'status_breakdown': status_breakdown
    }

async def get_recent_orders(
    db: AsyncSession,
    days: int = 7,
    limit: int = 20
) -> List[Order]:
    """Get recent orders from last N days"""
    date_from = datetime.utcnow() - timedelta(days=days)
    
    result = await db.execute(
        select(Order)
        .options(
            selectinload(Order.customer),
            selectinload(Order.service)
        )
        .where(Order.created_at >= date_from)
        .order_by(desc(Order.created_at))
        .limit(limit)
    )
    return result.scalars().all()

async def get_pending_orders_count(db: AsyncSession) -> int:
    """Get count of pending orders"""
    result = await db.execute(
        select(func.count(Order.id))
        .where(Order.status == OrderStatus.PENDING.value)
    )
    return result.scalar() or 0