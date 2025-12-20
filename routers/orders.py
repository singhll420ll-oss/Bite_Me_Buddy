from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import json

from database import get_db
from crud.order import (
    create_order, get_order_by_id, get_orders_by_customer,
    update_order_status, assign_order, generate_order_otp,
    verify_order_otp, get_order_statistics
)
from crud.service import get_service_by_id
from crud.user import get_user_by_id
from core.security import get_current_user
from core.twilio_client import twilio_client
from schemas.schemas import OrderStatus

router = APIRouter(tags=["orders"])
templates = Jinja2Templates(directory="templates")

@router.get("/cart", response_class=HTMLResponse)
async def cart_page(
    request: Request,
    service_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Cart page"""
    
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    
    service = None
    if service_id:
        service = await get_service_by_id(db, service_id)
    
    return templates.TemplateResponse(
        "cart.html",
        {
            "request": request,
            "service": service,
            "current_user": current_user
        }
    )

@router.post("/api/orders")
async def create_new_order(
    request: Request,
    service_id: int = Form(...),
    address: str = Form(...),
    phone: str = Form(...),
    special_instructions: Optional[str] = Form(None),
    items_json: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create new order"""
    
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Parse items
    try:
        items_data = json.loads(items_json)
        items = [(item["id"], item["quantity"]) for item in items_data]
    except:
        raise HTTPException(status_code=400, detail="Invalid items data")
    
    # Create order
    order = await create_order(
        db,
        current_user["id"],
        service_id,
        address,
        phone,
        special_instructions,
        items
    )
    
    if not order:
        raise HTTPException(status_code=400, detail="Failed to create order")
    
    # Redirect to my orders page
    return RedirectResponse(url="/myorders", status_code=303)

@router.get("/myorders", response_class=HTMLResponse)
async def my_orders(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """User's orders page"""
    
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    
    orders = await get_orders_by_customer(db, current_user["id"])
    
    return templates.TemplateResponse(
        "myorders.html",
        {
            "request": request,
            "orders": orders,
            "current_user": current_user
        }
    )

@router.get("/api/myorders")
async def api_my_orders(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """API endpoint for user's orders (HTMX)"""
    
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    orders = await get_orders_by_customer(db, current_user["id"])
    return orders

@router.post("/api/orders/{order_id}/assign")
async def assign_order_to_team(
    request: Request,
    order_id: int,
    team_member_id: int = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Assign order to team member (Admin only)"""
    
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    order = await assign_order(db, order_id, team_member_id)
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Get updated order for template
    order = await get_order_by_id(db, order_id)
    
    return templates.TemplateResponse(
        "partials/order_row.html",
        {
            "request": request,
            "order": order
        }
    )

@router.post("/api/orders/{order_id}/generate-otp")
async def generate_delivery_otp(
    request: Request,
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Generate OTP for delivery (Team Member only)"""
    
    if not current_user or current_user.get("role") != "team_member":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Check if order is assigned to this team member
    order = await get_order_by_id(db, order_id)
    if not order or order.assigned_to != current_user["id"]:
        raise HTTPException(status_code=403, detail="Order not assigned to you")
    
    # Generate OTP
    result = await generate_order_otp(db, order_id)
    
    if not result:
        raise HTTPException(status_code=400, detail="Cannot generate OTP")
    
    otp, otp_expiry = result
    
    # Send OTP via SMS
    if order.customer.phone:
        twilio_client.send_otp_sms(order.customer.phone, otp, order.order_number)
    
    return {
        "message": "OTP generated and sent",
        "otp_expiry": otp_expiry.isoformat()
    }

@router.post("/api/orders/{order_id}/verify-otp")
async def verify_delivery_otp(
    request: Request,
    order_id: int,
    otp: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Verify delivery OTP (Team Member only)"""
    
    if not current_user or current_user.get("role") != "team_member":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Check if order is assigned to this team member
    order = await get_order_by_id(db, order_id)
    if not order or order.assigned_to != current_user["id"]:
        raise HTTPException(status_code=403, detail="Order not assigned to you")
    
    # Verify OTP
    success = await verify_order_otp(db, order_id, otp)
    
    if success:
        return {"success": True, "message": "Delivery confirmed successfully"}
    else:
        return {"success": False, "message": "Invalid OTP or maximum attempts exceeded"}

@router.get("/admin/orders", response_class=HTMLResponse)
async def admin_orders_list(
    request: Request,
    status: Optional[str] = None,
    page: int = 1,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Admin orders management page"""
    
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    skip = (page - 1) * 20
    orders, total = await get_all_orders(db, skip=skip, limit=20, status=status)
    
    # Get team members for assignment dropdown
    from crud.user import get_users_by_role
    team_members = await get_users_by_role(db, "team_member", limit=1000)
    
    # Get statistics
    stats = await get_order_statistics(db)
    
    total_pages = (total + 19) // 20  # Ceiling division
    
    return templates.TemplateResponse(
        "admin_orders.html",
        {
            "request": request,
            "orders": orders,
            "team_members": team_members,
            "stats": stats,
            "current_status": status,
            "current_page": page,
            "total_pages": total_pages,
            "total": total,
            "current_user": current_user
        }
)
