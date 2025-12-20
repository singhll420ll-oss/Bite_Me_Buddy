from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import json

from database import get_db
from crud.order import get_orders_by_team_member, get_order_by_id
from crud.user import get_user_by_id
from crud.session import get_user_sessions
from core.security import get_current_user

router = APIRouter(tags=["team_member"])
templates = Jinja2Templates(directory="templates")

@router.get("/team/dashboard", response_class=HTMLResponse)
async def team_member_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Team member dashboard"""
    
    if not current_user or current_user.get("role") != "team_member":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Get assigned orders
    orders = await get_orders_by_team_member(db, current_user["id"])
    
    # Get team member details
    team_member = await get_user_by_id(db, current_user["id"])
    
    # Get today's sessions
    from datetime import date
    today_sessions, _ = await get_user_sessions(db, current_user["id"], date_from=date.today())
    
    return templates.TemplateResponse(
        "team_member_dashboard.html",
        {
            "request": request,
            "orders": orders,
            "team_member": team_member,
            "today_sessions": today_sessions,
            "current_user": current_user
        }
    )

@router.get("/api/team/orders")
async def api_team_orders(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """API endpoint for team member orders (HTMX)"""
    
    if not current_user or current_user.get("role") != "team_member":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    orders = await get_orders_by_team_member(db, current_user["id"])
    return orders

@router.get("/team/orders/{order_id}")
async def team_order_detail(
    request: Request,
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Team member order detail (HTMX)"""
    
    if not current_user or current_user.get("role") != "team_member":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    order = await get_order_by_id(db, order_id)
    
    if not order or order.assigned_to != current_user["id"]:
        raise HTTPException(status_code=403, detail="Order not assigned to you")
    
    return templates.TemplateResponse(
        "partials/team_order_detail.html",
        {
            "request": request,
            "order": order
        }
                           )
