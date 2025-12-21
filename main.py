from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager

from database import engine, init_db
from core.logging import setup_logging
from core.exceptions import global_exception_handler, AppException
from routers import auth, users, services, orders, admin, team_member

# Setup logging
logger = setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events"""
    # Startup
    logger.info("Starting Bite Me Buddy application")
    
    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Bite Me Buddy application")
    await engine.dispose()

# Create FastAPI app
app = FastAPI(
    title="Bite Me Buddy",
    description="Food Ordering System",
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

# ========== MAIN ROUTES ==========

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """NAYA homepage - index.html (Dashboard style)"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/old", response_class=HTMLResponse)
async def old_home(request: Request):
    """PURANA homepage - index2.html (Legacy home)"""
    return templates.TemplateResponse("index2.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def user_dashboard(request: Request):
    """User Dashboard - user_dashboard.html"""
    # Yahan aap database se user data fetch kar sakte hain
    user_data = {
        "name": "User",
        "email": "user@example.com",
        "total_orders": 5,
        "pending_orders": 2,
        "total_spent": 2500,
        "recent_orders": []  # Aap yahan database se data bhar sakte hain
    }
    return templates.TemplateResponse("user_dashboard.html", {"request": request, **user_data})

@app.get("/services", response_class=HTMLResponse)
async def services_page(request: Request):
    """Services Listing Page"""
    # Check if services exist in database
    services_list = []  # Yahan database se services fetch karein
    
    context = {
        "request": request,
        "services": services_list,
        "services_count": len(services_list)
    }
    
    return templates.TemplateResponse("services.html", context)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login Page"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Register Page"""
    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/cart", response_class=HTMLResponse)
async def cart_page(request: Request):
    """Cart Page"""
    return templates.TemplateResponse("cart.html", {"request": request})

@app.get("/myorders", response_class=HTMLResponse)
async def my_orders(request: Request):
    """My Orders Page"""
    return templates.TemplateResponse("myorders.html", {"request": request})

# ========== REDIRECT ROUTES (Old HTML files ke liye) ==========

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

# ========== CUSTOM API ENDPOINTS ==========

@app.get("/api/user/stats")
async def get_user_stats():
    """Get user statistics for dashboard"""
    return {
        "total_orders": 5,
        "pending_orders": 2,
        "completed_orders": 3,
        "total_spent": 2500,
        "favorite_services": ["Home Cleaning", "AC Servicing"]
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