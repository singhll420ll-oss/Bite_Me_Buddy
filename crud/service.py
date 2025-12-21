from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from sqlalchemy.orm import selectinload
from typing import Optional, List, Dict, Any
from datetime import datetime

from models.models import Service, MenuItem

# ========== SERVICE OPERATIONS ==========

async def create_service(db: AsyncSession, name: str, description: Optional[str] = None, image_url: Optional[str] = None) -> Service:
    """Create new service"""
    db_service = Service(
        name=name,
        description=description,
        image_url=image_url
    )
    db.add(db_service)
    await db.commit()
    await db.refresh(db_service)
    return db_service

async def get_service_by_id(db: AsyncSession, service_id: int) -> Optional[Service]:
    """Get service by ID with menu items"""
    result = await db.execute(
        select(Service)
        .options(selectinload(Service.menu_items))
        .where(and_(Service.id == service_id, Service.is_active == True))
    )
    return result.scalar_one_or_none()

async def get_all_services(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Service]:
    """Get all active services"""
    result = await db.execute(
        select(Service)
        .where(Service.is_active == True)
        .order_by(Service.name)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def update_service(db: AsyncSession, service_id: int, update_data: dict) -> Optional[Service]:
    """Update service"""
    await db.execute(
        update(Service)
        .where(Service.id == service_id)
        .values(**update_data)
    )
    await db.commit()
    return await get_service_by_id(db, service_id)

async def delete_service(db: AsyncSession, service_id: int) -> bool:
    """Soft delete service"""
    service = await get_service_by_id(db, service_id)
    if service:
        service.is_active = False
        await db.commit()
        return True
    return False

# ========== MENU ITEM OPERATIONS ==========

async def create_menu_item(db: AsyncSession, service_id: int, name: str, description: str, price: float, image_url: Optional[str] = None) -> MenuItem:
    """Create new menu item"""
    db_item = MenuItem(
        service_id=service_id,
        name=name,
        description=description,
        price=price,
        image_url=image_url
    )
    db.add(db_item)
    await db.commit()
    await db.refresh(db_item)
    return db_item

async def get_menu_item_by_id(db: AsyncSession, item_id: int) -> Optional[MenuItem]:
    """Get menu item by ID"""
    result = await db.execute(
        select(MenuItem).where(MenuItem.id == item_id)
    )
    return result.scalar_one_or_none()

async def get_menu_items_by_service(db: AsyncSession, service_id: int) -> List[MenuItem]:
    """Get all menu items for a service"""
    result = await db.execute(
        select(MenuItem)
        .where(and_(
            MenuItem.service_id == service_id,
            MenuItem.is_available == True
        ))
        .order_by(MenuItem.name)
    )
    return result.scalars().all()

async def update_menu_item(db: AsyncSession, item_id: int, update_data: dict) -> Optional[MenuItem]:
    """Update menu item"""
    await db.execute(
        update(MenuItem)
        .where(MenuItem.id == item_id)
        .values(**update_data)
    )
    await db.commit()
    return await get_menu_item_by_id(db, item_id)

async def delete_menu_item(db: AsyncSession, item_id: int) -> bool:
    """Soft delete menu item"""
    item = await get_menu_item_by_id(db, item_id)
    if item:
        item.is_available = False
        await db.commit()
        return True
    return False

# ========== SERVICE STATISTICS ==========

async def get_service_statistics(db: AsyncSession) -> Dict[str, Any]:
    """Get service statistics"""
    from sqlalchemy import func
    
    # Total services count
    total_result = await db.execute(
        select(func.count(Service.id))
        .where(Service.is_active == True)
    )
    total_services = total_result.scalar() or 0
    
    # Services with menu items count
    services_with_items_result = await db.execute(
        select(func.count(Service.id))
        .join(MenuItem, Service.menu_items)
        .where(and_(
            Service.is_active == True,
            MenuItem.is_available == True
        ))
        .distinct()
    )
    services_with_items = services_with_items_result.scalar() or 0
    
    # Total menu items
    menu_items_result = await db.execute(
        select(func.count(MenuItem.id))
        .where(MenuItem.is_available == True)
    )
    total_menu_items = menu_items_result.scalar() or 0
    
    # Average price of menu items
    avg_price_result = await db.execute(
        select(func.avg(MenuItem.price))
        .where(MenuItem.is_available == True)
    )
    avg_price = avg_price_result.scalar() or 0
    
    return {
        "total_services": total_services,
        "services_with_items": services_with_items,
        "total_menu_items": total_menu_items,
        "avg_menu_item_price": float(avg_price) if avg_price else 0.0
    }

async def get_popular_services(db: AsyncSession, limit: int = 5) -> List[Dict[str, Any]]:
    """Get popular services based on order count"""
    from sqlalchemy import func
    from models.models import Order
    
    result = await db.execute(
        select(
            Service.id,
            Service.name,
            func.count(Order.id).label('order_count')
        )
        .join(Order, Service.orders)
        .where(Service.is_active == True)
        .group_by(Service.id, Service.name)
        .order_by(func.count(Order.id).desc())
        .limit(limit)
    )
    
    popular_services = []
    for row in result.all():
        popular_services.append({
            "id": row[0],
            "name": row[1],
            "order_count": row[2]
        })
    
    return popular_services

async def search_services(db: AsyncSession, search_term: str) -> List[Service]:
    """Search services by name or description"""
    from sqlalchemy import or_
    
    result = await db.execute(
        select(Service)
        .where(and_(
            Service.is_active == True,
            or_(
                Service.name.ilike(f"%{search_term}%"),
                Service.description.ilike(f"%{search_term}%")
            )
        ))
        .order_by(Service.name)
    )
    return result.scalars().all()

async def search_menu_items(db: AsyncSession, search_term: str) -> List[MenuItem]:
    """Search menu items by name or description"""
    from sqlalchemy import or_
    
    result = await db.execute(
        select(MenuItem)
        .where(and_(
            MenuItem.is_available == True,
            or_(
                MenuItem.name.ilike(f"%{search_term}%"),
                MenuItem.description.ilike(f"%{search_term}%")
            )
        ))
        .order_by(MenuItem.name)
    )
    return result.scalars().all()