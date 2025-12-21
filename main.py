import os
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
import logging

from core.config import settings
from database import engine, Base, get_db
from routers import auth, users, services, orders, admin, team_member
from core.logging import setup_logging
from models import models
from schemas import schemas
from crud.crud import UserCRUD
from sqlalchemy.ext.asyncio import AsyncSession

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    logger.info("Starting Bite Me Buddy Application...")
    
    # Create database tables
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
    
    # Create upload directory
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Upload directory created at: {upload_dir}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Bite Me Buddy Application...")

# Create FastAPI app
app = FastAPI(
    title="Bite Me Buddy - Food Ordering System",
    description="Professional Food Ordering System with Admin Panel",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
)

# Add middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Include routers
app.include_router(auth.router, tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(services.router, prefix="/api/services", tags=["Services"])
app.include_router(orders.router, prefix="/api/orders", tags=["Orders"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(team_member.router, prefix="/api/team", tags=["Team Member"])

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global error: {exc}", exc_info=True)
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "error": str(exc)},
        status_code=500,
    )

# ==================== HELPER FUNCTIONS ====================

async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)):
    """Get current user from cookies"""
    user_id = request.cookies.get("user_id")
    if not user_id:
        return None
    
    try:
        user = await UserCRUD.get_by_id(db, int(user_id))
        return user
    except:
        return None

def check_user_role(user, required_role: str) -> bool:
    """Check if user has required role"""
    if not user:
        return False
    return user.role.value == required_role

# ==================== ROOT & PUBLIC ROUTES ====================

@app.get("/")
async def root():
    """Serve your old index.html file"""
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    else:
        # Fallback to Bite Me Buddy home
        return RedirectResponse(url="/bite-me-buddy")

@app.get("/bite-me-buddy")
async def bite_me_buddy_home(request: Request):
    """Bite Me Buddy home page with secret clock"""
    return templates.TemplateResponse(
        "index2.html",
        {"request": request, "title": "Bite Me Buddy"}
    )

# ==================== PUBLIC PAGES (No login required) ====================

@app.get("/register")
async def register_page(request: Request):
    """Registration page -任何人都可以访问"""
    return templates.TemplateResponse(
        "register.html",
        {"request": request, "title": "Register - Bite Me Buddy"}
    )

@app.get("/login")
async def login_page(request: Request):
    """Login page -任何人都可以访问"""
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "title": "Login - Bite Me Buddy"}
    )

@app.get("/team-login")
async def team_login_page(request: Request):
    """Team member login page -任何人都可以访问"""
    return templates.TemplateResponse(
        "team_login.html",
        {"request": request, "title": "Team Member Login"}
    )

@app.get("/admin-login")
async def admin_login_page(request: Request):
    """Admin login page (accessed via secret clock) -任何人都可以访问"""
    return templates.TemplateResponse(
        "admin_login.html",
        {"request": request, "title": "Admin Login"}
    )

# ==================== CUSTOMER ROUTES ====================

@app.get("/customer/dashboard")
async def customer_dashboard_route(request: Request, db: AsyncSession = Depends(get_db)):
    """Customer dashboard - Requires customer login"""
    user = await get_current_user(request, db)
    
    if not user:
        # Not logged in, redirect to login
        return RedirectResponse(url="/login")
    
    if user.role.value != "customer":
        # Wrong role, redirect based on role
        if user.role.value == "admin":
            return RedirectResponse(url="/admin/dashboard")
        elif user.role.value == "team_member":
            return RedirectResponse(url="/team/dashboard")
        else:
            return RedirectResponse(url="/login")
    
    # Customer is logged in, show dashboard
    return templates.TemplateResponse(
        "customer_dashboard.html",
        {
            "request": request,
            "title": "My Dashboard - Bite Me Buddy",
            "user": user,
            "active_tab": "dashboard"
        }
    )

@app.get("/customer/profile")
async def customer_profile_route(request: Request, db: AsyncSession = Depends(get_db)):
    """Customer profile page - Requires customer login"""
    user = await get_current_user(request, db)
    
    if not user or user.role.value != "customer":
        return RedirectResponse(url="/login")
    
    return templates.TemplateResponse(
        "customer_profile.html",
        {
            "request": request,
            "title": "My Profile - Bite Me Buddy",
            "user": user,
            "active_tab": "profile"
        }
    )

@app.get("/customer/cart")
async def customer_cart_route(request: Request, db: AsyncSession = Depends(get_db)):
    """Customer cart page - Requires customer login"""
    user = await get_current_user(request, db)
    
    if not user or user.role.value != "customer":
        return RedirectResponse(url="/login")
    
    return templates.TemplateResponse(
        "customer_cart.html",
        {
            "request": request,
            "title": "My Cart - Bite Me Buddy",
            "user": user,
            "active_tab": "cart"
        }
    )

@app.get("/customer/orders")
async def customer_orders_route(request: Request, db: AsyncSession = Depends(get_db)):
    """Customer orders history - Requires customer login"""
    user = await get_current_user(request, db)
    
    if not user or user.role.value != "customer":
        return RedirectResponse(url="/login")
    
    return templates.TemplateResponse(
        "customer_orders.html",
        {
            "request": request,
            "title": "My Orders - Bite Me Buddy",
            "user": user,
            "active_tab": "orders"
        }
    )

@app.get("/customer/checkout")
async def customer_checkout_route(request: Request, db: AsyncSession = Depends(get_db)):
    """Checkout page - Requires customer login"""
    user = await get_current_user(request, db)
    
    if not user or user.role.value != "customer":
        return RedirectResponse(url="/login")
    
    return templates.TemplateResponse(
        "customer_checkout.html",
        {
            "request": request,
            "title": "Checkout - Bite Me Buddy",
            "user": user,
            "active_tab": "cart"
        }
    )

# ==================== SERVICES PAGES ====================

@app.get("/services")
async def services_page_route(request: Request, db: AsyncSession = Depends(get_db)):
    """Services listing page - Requires customer login"""
    user = await get_current_user(request, db)
    
    if not user or user.role.value != "customer":
        return RedirectResponse(url="/login")
    
    from crud.crud import ServiceCRUD
    services = await ServiceCRUD.get_all(db)
    
    return templates.TemplateResponse(
        "services.html",
        {
            "request": request,
            "title": "Services - Bite Me Buddy",
            "user": user,
            "services": services,
            "active_tab": "services"
        }
    )

@app.get("/service/{service_id}")
async def service_menu_route(request: Request, service_id: int, db: AsyncSession = Depends(get_db)):
    """Service menu page - Requires customer login"""
    user = await get_current_user(request, db)
    
    if not user or user.role.value != "customer":
        return RedirectResponse(url="/login")
    
    from crud.crud import ServiceCRUD, MenuItemCRUD
    
    service = await ServiceCRUD.get_by_id(db, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    menu_items = await MenuItemCRUD.get_by_service(db, service_id)
    
    return templates.TemplateResponse(
        "service_menu.html",
        {
            "request": request,
            "title": f"{service.name} - Bite Me Buddy",
            "user": user,
            "service": service,
            "menu_items": menu_items
        }
    )

# ==================== ADMIN ROUTES ====================

@app.get("/admin/dashboard")
async def admin_dashboard_route(request: Request, db: AsyncSession = Depends(get_db)):
    """Admin dashboard - Requires admin login"""
    user = await get_current_user(request, db)
    
    if not user:
        return RedirectResponse(url="/admin-login")
    
    if user.role.value != "admin":
        # Wrong role, redirect based on role
        if user.role.value == "customer":
            return RedirectResponse(url="/customer/dashboard")
        elif user.role.value == "team_member":
            return RedirectResponse(url="/team/dashboard")
        else:
            return RedirectResponse(url="/admin-login")
    
    # Admin is logged in, show dashboard
    from crud.crud import OrderCRUD
    stats = await OrderCRUD.get_dashboard_stats(db)
    
    return templates.TemplateResponse(
        "admin_dashboard.html",
        {
            "request": request,
            "title": "Admin Dashboard - Bite Me Buddy",
            "admin": user,
            "stats": stats,
            "active_tab": "dashboard"
        }
    )

@app.get("/admin/services")
async def admin_services_route(request: Request, db: AsyncSession = Depends(get_db)):
    """Manage services - Requires admin login"""
    user = await get_current_user(request, db)
    
    if not user or user.role.value != "admin":
        return RedirectResponse(url="/admin-login")
    
    from crud.crud import ServiceCRUD
    services = await ServiceCRUD.get_all(db)
    
    return templates.TemplateResponse(
        "admin_services.html",
        {
            "request": request,
            "title": "Manage Services - Admin",
            "admin": user,
            "services": services,
            "active_tab": "services"
        }
    )

@app.get("/admin/orders")
async def admin_orders_route(request: Request, db: AsyncSession = Depends(get_db)):
    """Manage orders - Requires admin login"""
    user = await get_current_user(request, db)
    
    if not user or user.role.value != "admin":
        return RedirectResponse(url="/admin-login")
    
    from crud.crud import OrderCRUD, UserCRUD
    orders = await OrderCRUD.get_all(db)
    team_members = await UserCRUD.get_team_members(db)
    
    return templates.TemplateResponse(
        "admin_orders.html",
        {
            "request": request,
            "title": "Manage Orders - Admin",
            "admin": user,
            "orders": orders,
            "team_members": team_members,
            "active_tab": "orders"
        }
    )

@app.get("/admin/customers")
async def admin_customers_route(request: Request, db: AsyncSession = Depends(get_db)):
    """Manage customers - Requires admin login"""
    user = await get_current_user(request, db)
    
    if not user or user.role.value != "admin":
        return RedirectResponse(url="/admin-login")
    
    from crud.crud import UserCRUD
    customers = await UserCRUD.get_customers(db)
    
    return templates.TemplateResponse(
        "admin_customers.html",
        {
            "request": request,
            "title": "Manage Customers - Admin",
            "admin": user,
            "customers": customers,
            "active_tab": "customers"
        }
    )

@app.get("/admin/customers/{customer_id}")
async def admin_customer_detail_route(request: Request, customer_id: int, db: AsyncSession = Depends(get_db)):
    """Customer detail page - Requires admin login"""
    user = await get_current_user(request, db)
    
    if not user or user.role.value != "admin":
        return RedirectResponse(url="/admin-login")
    
    from crud.crud import UserCRUD, OrderCRUD, UserSessionCRUD
    customer = await UserCRUD.get_by_id(db, customer_id)
    
    if not customer or customer.role.value != "customer":
        raise HTTPException(status_code=404, detail="Customer not found")
    
    orders = await OrderCRUD.get_by_customer(db, customer_id)
    sessions = await UserSessionCRUD.get_user_sessions(db, customer_id)
    
    return templates.TemplateResponse(
        "admin_customer_detail.html",
        {
            "request": request,
            "title": f"Customer Details - {customer.name}",
            "admin": user,
            "customer": customer,
            "orders": orders,
            "sessions": sessions,
            "active_tab": "customers"
        }
    )

@app.get("/admin/team-members")
async def admin_team_members_route(request: Request, db: AsyncSession = Depends(get_db)):
    """Manage team members - Requires admin login"""
    user = await get_current_user(request, db)
    
    if not user or user.role.value != "admin":
        return RedirectResponse(url="/admin-login")
    
    from crud.crud import UserCRUD
    team_members = await UserCRUD.get_team_members(db)
    
    return templates.TemplateResponse(
        "admin_team_members.html",
        {
            "request": request,
            "title": "Manage Team Members - Admin",
            "admin": user,
            "team_members": team_members,
            "active_tab": "team_members"
        }
    )

@app.get("/admin/plans")
async def admin_plans_route(request: Request, db: AsyncSession = Depends(get_db)):
    """Team member plans - Requires admin login"""
    user = await get_current_user(request, db)
    
    if not user or user.role.value != "admin":
        return RedirectResponse(url="/admin-login")
    
    from crud.crud import UserCRUD
    team_members = await UserCRUD.get_team_members(db)
    
    return templates.TemplateResponse(
        "admin_plans.html",
        {
            "request": request,
            "title": "Team Member Plans - Admin",
            "admin": user,
            "team_members": team_members,
            "active_tab": "plans"
        }
    )

@app.get("/admin/reports/online-time")
async def admin_reports_route(request: Request, db: AsyncSession = Depends(get_db)):
    """Online time reports - Requires admin login"""
    user = await get_current_user(request, db)
    
    if not user or user.role.value != "admin":
        return RedirectResponse(url="/admin-login")
    
    from crud.crud import UserCRUD, UserSessionCRUD
    
    customers = await UserCRUD.get_customers(db)
    team_members = await UserCRUD.get_team_members(db)
    
    customer_reports = []
    for customer in customers:
        report = await UserSessionCRUD.get_online_time_report(db, customer.id)
        customer_reports.append({
            "user": customer,
            "report": report
        })
    
    team_member_reports = []
    for member in team_members:
        report = await UserSessionCRUD.get_online_time_report(db, member.id)
        team_member_reports.append({
            "user": member,
            "report": report
        })
    
    return templates.TemplateResponse(
        "admin_reports.html",
        {
            "request": request,
            "title": "Online Time Reports - Admin",
            "admin": user,
            "customer_reports": customer_reports,
            "team_member_reports": team_member_reports,
            "active_tab": "reports"
        }
    )

# ==================== TEAM MEMBER ROUTES ====================

@app.get("/team/dashboard")
async def team_dashboard_route(request: Request, db: AsyncSession = Depends(get_db)):
    """Team member dashboard - Requires team member login"""
    user = await get_current_user(request, db)
    
    if not user:
        return RedirectResponse(url="/team-login")
    
    if user.role.value != "team_member":
        # Wrong role, redirect based on role
        if user.role.value == "admin":
            return RedirectResponse(url="/admin/dashboard")
        elif user.role.value == "customer":
            return RedirectResponse(url="/customer/dashboard")
        else:
            return RedirectResponse(url="/team-login")
    
    # Team member is logged in, show dashboard
    from sqlalchemy import select
    from models import models
    
    # Get assigned orders
    result = await db.execute(
        select(models.Order)
        .options(
            select(models.Order.customer),
            select(models.Order.service),
            select(models.Order.items).select(models.OrderItem.menu_item)
        )
        .where(models.Order.assigned_to == user.id)
        .where(models.Order.status.in_(["confirmed", "preparing", "out_for_delivery"]))
        .order_by(models.Order.created_at.desc())
    )
    assigned_orders = result.scalars().all()
    
    # Get today's plans
    from crud.crud import TeamMemberPlanCRUD
    plans = await TeamMemberPlanCRUD.get_by_team_member(db, user.id)
    
    return templates.TemplateResponse(
        "team_member_dashboard.html",
        {
            "request": request,
            "title": "Team Member Dashboard - Bite Me Buddy",
            "member": user,
            "assigned_orders": assigned_orders,
            "plans": plans,
            "active_tab": "dashboard"
        }
    )

@app.get("/team/profile")
async def team_profile_route(request: Request, db: AsyncSession = Depends(get_db)):
    """Team member profile - Requires team member login"""
    user = await get_current_user(request, db)
    
    if not user or user.role.value != "team_member":
        return RedirectResponse(url="/team-login")
    
    return templates.TemplateResponse(
        "team_member_profile.html",
        {
            "request": request,
            "title": "My Profile - Team Member",
            "member": user,
            "active_tab": "profile"
        }
    )

# ==================== LOGOUT ROUTE ====================

@app.get("/logout")
async def logout_route(request: Request, db: AsyncSession = Depends(get_db)):
    """Logout all users"""
    # Clear cookies
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token")
    response.delete_cookie("user_id")
    response.delete_cookie("session_id")
    
    return response

# ==================== HEALTH CHECK ====================

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "Bite Me Buddy"}

# ==================== ERROR PAGES ====================

@app.get("/error")
async def error_page(request: Request, message: str = "An error occurred"):
    """Error page"""
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "error": message}
    )

# ==================== FALLBACK ROUTE ====================

@app.get("/{path:path}")
async def catch_all(path: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Catch all undefined routes"""
    # Try to see if user is logged in
    user = await get_current_user(request, db)
    
    if user:
        # User is logged in, redirect based on role
        if user.role.value == "customer":
            return RedirectResponse(url="/customer/dashboard")
        elif user.role.value == "admin":
            return RedirectResponse(url="/admin/dashboard")
        elif user.role.value == "team_member":
            return RedirectResponse(url="/team/dashboard")
    
    # Not logged in, redirect to home
    return RedirectResponse(url="/")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=settings.DEBUG,
        log_level="info" if settings.DEBUG else "warning"
    )