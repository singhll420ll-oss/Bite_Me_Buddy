from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import json

from database import get_db
from crud.user import (
    get_all_users, get_users_by_role, create_user,
    update_user, delete_user, get_user_by_id
)
from crud.session import get_online_time_report, get_all_user_sessions
from crud.service import get_all_services
from crud.order import get_all_orders, get_order_statistics
from schemas.schemas import UserCreate, UserRole, OrderStatus
from core.security import get_current_user, get_password_hash
from utils.file_upload import save_upload_file
from core.twilio_client import twilio_client

router = APIRouter(tags=["admin"])
templates = Jinja2Templates(directory="templates")

@router.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Admin dashboard"""
    
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Get statistics
    order_stats = await get_order_statistics(db)
    
    # Get recent orders
    recent_orders, _ = await get_all_orders(db, limit=10)
    
    # Get team members
    team_members = await get_users_by_role(db, UserRole.TEAM_MEMBER, limit=10)
    
    # Get customers
    customers = await get_users_by_role(db, UserRole.CUSTOMER, limit=10)
    
    # Get online time report
    online_report = await get_online_time_report(db)
    
    return templates.TemplateResponse(
        "admin_dashboard.html",
        {
            "request": request,
            "order_stats": order_stats,
            "recent_orders": recent_orders,
            "team_members": team_members,
            "customers": customers,
            "online_report": online_report,
            "current_user": current_user
        }
    )

@router.get("/admin/team-members", response_class=HTMLResponse)
async def admin_team_members(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Team members management page"""
    
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    team_members = await get_users_by_role(db, UserRole.TEAM_MEMBER, limit=1000)
    
    return templates.TemplateResponse(
        "admin_team_members.html",
        {
            "request": request,
            "team_members": team_members,
            "current_user": current_user
        }
    )

@router.post("/admin/team-members")
async def admin_create_team_member(
    request: Request,
    name: str = Form(...),
    username: str = Form(...),
    email: Optional[str] = Form(None),
    phone: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create new team member (Admin only)"""
    
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Create user data
    user_data = UserCreate(
        name=name,
        username=username,
        email=email,
        phone=phone,
        password=password,
        role=UserRole.TEAM_MEMBER
    )
    
    # Create user
    user = await create_user(db, user_data)
    
    return templates.TemplateResponse(
        "partials/team_member_row.html",
        {
            "request": request,
            "member": user
        }
    )

@router.put("/admin/team-members/{member_id}")
async def admin_update_team_member(
    request: Request,
    member_id: int,
    name: str = Form(...),
    username: str = Form(...),
    email: Optional[str] = Form(None),
    phone: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update team member (Admin only)"""
    
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    update_data = {
        "name": name,
        "username": username,
        "email": email,
        "phone": phone
    }
    
    user = await update_user(db, member_id, update_data)
    
    if not user:
        raise HTTPException(status_code=404, detail="Team member not found")
    
    return templates.TemplateResponse(
        "partials/team_member_row.html",
        {
            "request": request,
            "member": user
        }
    )

@router.delete("/admin/team-members/{member_id}")
async def admin_delete_team_member(
    member_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete team member (Admin only)"""
    
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    success = await delete_user(db, member_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Team member not found")
    
    return {"message": "Team member deleted successfully"}

@router.get("/admin/reports/online-time")
async def admin_online_time_report(
    request: Request,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Online time report (Admin only)"""
    
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    from datetime import datetime
    date_from_obj = datetime.strptime(date_from, "%Y-%m-%d") if date_from else None
    date_to_obj = datetime.strptime(date_to, "%Y-%m-%d") if date_to else None
    
    report = await get_online_time_report(db, date_from_obj, date_to_obj)
    
    return templates.TemplateResponse(
        "partials/online_time_report.html",
        {
            "request": request,
            "report": report
        }
    )

@router.get("/admin/reports/user-sessions")
async def admin_user_sessions_report(
    request: Request,
    user_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = 1,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """User sessions report (Admin only)"""
    
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    from datetime import datetime
    date_from_obj = datetime.strptime(date_from, "%Y-%m-%d").date() if date_from else None
    date_to_obj = datetime.strptime(date_to, "%Y-%m-%d").date() if date_to else None
    
    skip = (page - 1) * 50
    sessions, total = await get_all_user_sessions(
        db,
        date_from=date_from_obj,
        date_to=date_to_obj,
        skip=skip,
        limit=50
    )
    
    # Get user if specified
    user = None
    if user_id:
        user = await get_user_by_id(db, user_id)
    
    total_pages = (total + 49) // 50
    
    return templates.TemplateResponse(
        "partials/user_sessions_report.html",
        {
            "request": request,
            "sessions": sessions,
            "user": user,
            "current_page": page,
            "total_pages": total_pages,
            "total": total
        }
    )

@router.post("/admin/upload")
async def admin_upload_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload file (Admin only)"""
    
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    file_url = await save_upload_file(file, "admin")
    
    if not file_url:
        raise HTTPException(status_code=400, detail="Failed to upload file")
    
    return {"url": f"/static/{file_url}"}
