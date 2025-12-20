from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from sqlalchemy.orm import selectinload
from typing import Optional, List
from datetime import datetime

from models.models import Service, MenuItem

async def create_service(db: AsyncSession, name: str, description: Optional[str] = None) -> Service:
    """Create new service"""
    db_service = Service(
        name=name,
        description=description
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

async def create_menu_item(db: AsyncSession, service_id: int, name: str, description: str, price: float) -> MenuItem:
    """Create new menu item"""
    db_item = MenuItem(
        service_id=service_id,
        name=name,
        description=description,
        price=price
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
        .where(and_(MenuItem.service_id == service_id, MenuItem.is_available == True))
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
