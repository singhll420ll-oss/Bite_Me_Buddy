from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from database import get_db
from crud.user import get_all_users, get_users_by_role, get_customer_with_stats
from crud.order import get_orders_by_customer
from crud.session import get_user_sessions
from schemas.schemas import UserRole
from core.security import get_current_user

router = APIRouter(tags=["users"])
templates = Jinja2Templates(directory="templates")

@router.get("/customers", response_class=HTMLResponse)
async def customers_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """List all customers (Admin only)"""
    
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    customers = await get_users_by_role(db, UserRole.CUSTOMER, limit=1000)
    
    return templates.TemplateResponse(
        "customers_list.html",
        {
            "request": request,
            "customers": customers,
            "current_user": current_user
        }
    )

@router.get("/customers/{customer_id}", response_class=HTMLResponse)
async def customer_detail(
    request: Request,
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Customer detail page (Admin only)"""
    
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Get customer with stats
    customer_data = await get_customer_with_stats(db, customer_id)
    if not customer_data:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Get customer orders
    orders = await get_orders_by_customer(db, customer_id, limit=50)
    
    # Get customer sessions
    sessions, _ = await get_user_sessions(db, customer_id, limit=50)
    
    return templates.TemplateResponse(
        "customer_detail.html",
        {
            "request": request,
            "customer": customer_data["user"],
            "stats": {
                "total_orders": customer_data["total_orders"],
                "total_spent": customer_data["total_spent"],
                "last_order_date": customer_data["last_order_date"]
            },
            "orders": orders,
            "sessions": sessions,
            "current_user": current_user
        }
    )

@router.get("/api/customers")
async def api_customers_list(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """API endpoint for customers list (HTMX)"""
    
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    customers = await get_users_by_role(db, UserRole.CUSTOMER, limit=1000)
    
    return customers
