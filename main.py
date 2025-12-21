# main.py - UPDATED VERSION
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
import logging
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session

# ✅ CORRECTED IMPORTS: Import Base from database, NOT from models
from database import engine, get_db, Base  # Base is defined in database.py
from core.logging import setup_logging
from core.exceptions import global_exception_handler, AppException
from routers import auth, users, services, orders, admin, team_member
import jwt
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logger = setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events"""
    # Startup
    logger.info("🚀 Starting Bite Me Buddy application")
    
    # Create database tables
    try:
        logger.info("🗄️ Creating database tables...")
        # Import models AFTER startup to avoid circular imports
        from models.models import User, Service, Order, MenuItem, OrderItem, TeamMemberPlan, UserSession
        
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("✅ Database tables created successfully")
        
        # Test database connection
        try:
            from database import test_connection
            await test_connection()
        except Exception as e:
            logger.warning(f"⚠️ Database connection test: {e}")
            
    except Exception as e:
        logger.error(f"❌ Failed to create database tables: {e}")
        import traceback
        traceback.print_exc()
    
    yield
    
    # Shutdown
    logger.info("👋 Shutting down Bite Me Buddy application")

# Create FastAPI app
app = FastAPI(
    title="Bite Me Buddy",
    description="Food Ordering System with Mobile Authentication",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

# JWT configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"

# Register global exception handler
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(AppException, global_exception_handler)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(services.router, prefix="/api/services", tags=["Services"])
app.include_router(orders.router, prefix="/api/orders", tags=["Orders"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(team_member.router, prefix="/api/team", tags=["Team Member"])

# ========== AUTHENTICATION DEPENDENCY ==========

async def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: Session = Depends(get_db)
):
    """Get current authenticated user from JWT token"""
    from fastapi import HTTPException, status
    
    # If no token provided, return None for public routes
    if not token:
        return None
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Import here to avoid circular imports
        from crud import get_user_by_mobile
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        mobile: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        
        if mobile is None or user_id is None:
            raise credentials_exception
            
    except jwt.PyJWTError:
        raise credentials_exception
    
    user = get_user_by_mobile(db, mobile=mobile)
    if user is None or user.id != user_id:
        raise credentials_exception
    
    # Convert to Pydantic response
    from schemas import UserResponse
    return UserResponse.model_validate(user)

# ========== MAIN ROUTES ==========

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Homepage"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login Page"""
    return templates.TemplateResponse("auth/login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Register Page"""
    return templates.TemplateResponse("auth/register.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def user_dashboard(request: Request, current_user = Depends(get_current_user)):
    """User Dashboard - Protected route"""
    if not current_user:
        return RedirectResponse(url="/login")
    
    # Import here to avoid circular imports
    from crud import get_user_order_stats
    
    user_data = {
        "name": current_user.name or "User",
        "mobile": current_user.mobile,
        "user_id": current_user.id,
        "email": current_user.email or "",
        "role": current_user.role,
        "total_orders": 0,
        "pending_orders": 0,
        "total_spent": 0,
        "recent_orders": []
    }
    
    # Try to get actual stats
    try:
        db = next(get_db())
        stats = get_user_order_stats(db, current_user.id)
        if stats:
            user_data.update({
                "total_orders": stats.get("total_orders", 0),
                "pending_orders": stats.get("pending_orders", 0),
                "total_spent": stats.get("total_spent", 0)
            })
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
    
    return templates.TemplateResponse("user_dashboard.html", {
        "request": request,
        **user_data,
        "user": current_user
    })

@app.get("/services", response_class=HTMLResponse)
async def services_page(request: Request):
    """Services Listing Page"""
    # Import here to avoid circular imports
    from crud import get_all_services
    
    try:
        db = next(get_db())
        services_list = get_all_services(db)
    except Exception as e:
        logger.error(f"Error loading services: {e}")
        services_list = []
    
    context = {
        "request": request,
        "services": services_list,
        "services_count": len(services_list)
    }
    return templates.TemplateResponse("services.html", context)

@app.get("/cart", response_class=HTMLResponse)
async def cart_page(request: Request, current_user = Depends(get_current_user)):
    """Cart Page - Protected"""
    if not current_user:
        return RedirectResponse(url="/login")
    
    return templates.TemplateResponse("cart.html", {
        "request": request,
        "user": current_user
    })

@app.get("/myorders", response_class=HTMLResponse)
async def my_orders(request: Request, current_user = Depends(get_current_user)):
    """My Orders Page - Protected"""
    if not current_user:
        return RedirectResponse(url="/login")
    
    # Import here to avoid circular imports
    from crud import get_user_orders
    
    try:
        db = next(get_db())
        orders_list = get_user_orders(db, current_user.id, limit=10)
    except Exception as e:
        logger.error(f"Error loading orders: {e}")
        orders_list = []
    
    return templates.TemplateResponse("myorders.html", {
        "request": request,
        "user": current_user,
        "orders": orders_list
    })

@app.get("/profile", response_class=HTMLResponse)
async def user_profile(request: Request, current_user = Depends(get_current_user)):
    """User Profile Page - Protected"""
    if not current_user:
        return RedirectResponse(url="/login")
    
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": current_user
    })

# ========== LOGOUT ROUTE ==========

@app.get("/logout")
async def logout():
    """Logout user - Clear token client-side"""
    response = RedirectResponse(url="/login")
    response.delete_cookie("access_token")
    return response

# ========== HEALTH CHECK & INFO ==========

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "service": "Bite Me Buddy",
        "database": "PostgreSQL",
        "authentication": "JWT + Mobile OTP"
    }

@app.get("/api/info")
async def app_info():
    """Get application information"""
    return {
        "app_name": "Bite Me Buddy",
        "version": "1.0.0",
        "description": "Food Ordering System with Mobile Authentication",
        "features": [
            "Mobile-based authentication",
            "JWT token security",
            "Real-time order tracking",
            "Multi-role support (Customer, Team Member, Admin)",
            "OTP verification for deliveries"
        ],
        "database": "PostgreSQL",
        "api_docs": "/docs",
        "redoc": "/redoc"
    }

# ========== ERROR HANDLERS ==========

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors"""
    return templates.TemplateResponse(
        "404.html",
        {"request": request},
        status_code=404
    )

# ========== CUSTOM MIDDLEWARE ==========

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests"""
    logger.info(f"📥 Request: {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        logger.info(f"📤 Response: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"❌ Request error: {e}")
        raise

# ========== APPLICATION STARTUP ==========

if __name__ == "__main__":
    import uvicorn
    
    print("""
    🍔 BITE ME BUDDY - Food Ordering System
    ========================================
    📡 Starting server...
    🗄️  Database: PostgreSQL
    🔐 Auth: JWT + Mobile OTP
    🚀 API Docs: http://localhost:8000/docs
    📊 ReDoc: http://localhost:8000/redoc
    """)
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True
    )