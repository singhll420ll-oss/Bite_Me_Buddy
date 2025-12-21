from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
import logging
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session

from database import engine, get_db
from models import Base
from core.logging import setup_logging
from core.exceptions import global_exception_handler, AppException
from routers import auth, users, services, orders, admin, team_member
from schemas import UserResponse
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
    logger.info("Starting Bite Me Buddy application")
    
    # Create database tables
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Bite Me Buddy application")

# Create FastAPI app
app = FastAPI(
    title="Bite Me Buddy",
    description="Food Ordering System with Mobile Authentication",
    version="1.0.0",
    lifespan=lifespan
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
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# JWT configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"

# Register global exception handler
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(AppException, global_exception_handler)

# Include routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(services.router)
app.include_router(orders.router)
app.include_router(admin.router)
app.include_router(team_member.router)

# ========== AUTHENTICATION DEPENDENCY ==========

async def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: Session = Depends(get_db)
):
    """Get current authenticated user from JWT token"""
    from fastapi import HTTPException, status
    from crud import get_user_by_mobile
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        mobile: str = payload.get("sub")
        if mobile is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    
    user = get_user_by_mobile(db, mobile=mobile)
    if user is None:
        raise credentials_exception
    
    return user

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
async def user_dashboard(request: Request, current_user: UserResponse = Depends(get_current_user)):
    """User Dashboard - Protected route"""
    user_data = {
        "name": "User",
        "mobile": current_user.mobile,
        "user_id": current_user.id,
        "total_orders": 5,
        "pending_orders": 2,
        "total_spent": 2500,
        "recent_orders": []
    }
    return templates.TemplateResponse("user_dashboard.html", {
        "request": request, 
        **user_data,
        "user": current_user
    })

@app.get("/services", response_class=HTMLResponse)
async def services_page(request: Request):
    """Services Listing Page"""
    services_list = []
    context = {
        "request": request,
        "services": services_list,
        "services_count": len(services_list)
    }
    return templates.TemplateResponse("services.html", context)

@app.get("/cart", response_class=HTMLResponse)
async def cart_page(request: Request, current_user: UserResponse = Depends(get_current_user)):
    """Cart Page - Protected"""
    return templates.TemplateResponse("cart.html", {
        "request": request,
        "user": current_user
    })

@app.get("/myorders", response_class=HTMLResponse)
async def my_orders(request: Request, current_user: UserResponse = Depends(get_current_user)):
    """My Orders Page - Protected"""
    return templates.TemplateResponse("myorders.html", {
        "request": request,
        "user": current_user
    })

@app.get("/profile", response_class=HTMLResponse)
async def user_profile(request: Request, current_user: UserResponse = Depends(get_current_user)):
    """User Profile Page - Protected"""
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

# ========== REDIRECT ROUTES ==========

@app.get("/index2.html")
async def redirect_index2():
    """Redirect index2.html to /old"""
    return RedirectResponse(url="/old")

@app.get("/index.html")
async def redirect_old_index():
    """Redirect old index.html to /"""
    return RedirectResponse(url="/")

# ========== CUSTOM MIDDLEWARE ==========

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests"""
    logger.info(f"Request: {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Response: {response.status_code}")
    return response

# ========== ERROR HANDLERS ==========

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors"""
    return templates.TemplateResponse(
        "404.html",
        {"request": request},
        status_code=404
    )

# ========== HEALTH CHECK ==========

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Bite Me Buddy"}

# ========== API ENDPOINTS ==========

@app.get("/api/user/stats")
async def get_user_stats(current_user: UserResponse = Depends(get_current_user)):
    """Get user statistics for dashboard - Protected"""
    return {
        "mobile": current_user.mobile,
        "user_id": current_user.id,
        "total_orders": 5,
        "pending_orders": 2,
        "completed_orders": 3,
        "total_spent": 2500,
        "favorite_services": ["Home Cleaning", "AC Servicing"]
    }

@app.get("/api/user/profile")
async def get_user_profile(current_user: UserResponse = Depends(get_current_user)):
    """Get current user profile - Protected"""
    return {
        "id": current_user.id,
        "mobile": current_user.mobile,
        "created_at": current_user.created_at
    }

# ========== APPLICATION INFO ==========

@app.get("/api/info")
async def app_info():
    """Get application information"""
    return {
        "app_name": "Bite Me Buddy",
        "version": "1.0.0",
        "features": [
            "Mobile-based authentication",
            "JWT token security",
            "Protected dashboard",
            "Order management"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )