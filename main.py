from fastapi import FastAPI, Request, Depends, HTTPException, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timedelta
from typing import Optional
import os
import uuid
import json
from passlib.context import CryptContext
from jose import JWTError, jwt
from dotenv import load_dotenv
import uvicorn

# Load environment variables
load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost/bite_me_buddy")

# Create FastAPI app
app = FastAPI(
    title="Bite Me Buddy - Food Ordering System",
    description="Professional Food Ordering Platform",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS middleware
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
templates = Jinja2Templates(directory="templates")

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Database setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# =================== DATABASE MODELS ===================

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    phone = Column(String(20))
    password = Column(String(255), nullable=False)
    address = Column(Text)
    role = Column(String(20), default="customer")  # customer, team_member, admin
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    orders = relationship("Order", back_populates="customer")
    sessions = relationship("UserSession", back_populates="user")

class Service(Base):
    __tablename__ = "services"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    image_url = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    menu_items = relationship("MenuItem", back_populates="service")
    orders = relationship("Order", back_populates="service")

class MenuItem(Base):
    __tablename__ = "menu_items"
    
    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    price = Column(Float, nullable=False)
    image_url = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    service = relationship("Service", back_populates="menu_items")
    order_items = relationship("OrderItem", back_populates="menu_item")

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    total_amount = Column(Float, nullable=False)
    address = Column(Text, nullable=False)
    status = Column(String(20), default="pending")  # pending, confirmed, preparing, out_for_delivery, delivered, cancelled
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)
    otp = Column(String(6), nullable=True)
    otp_expiry = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    customer = relationship("User", foreign_keys=[customer_id], back_populates="orders")
    service = relationship("Service", back_populates="orders")
    team_member = relationship("User", foreign_keys=[assigned_to])
    order_items = relationship("OrderItem", back_populates="order")

class OrderItem(Base):
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    menu_item_id = Column(Integer, ForeignKey("menu_items.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    price_at_time = Column(Float, nullable=False)
    
    # Relationships
    order = relationship("Order", back_populates="order_items")
    menu_item = relationship("MenuItem", back_populates="order_items")

class TeamMemberPlan(Base):
    __tablename__ = "team_member_plans"
    
    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    team_member_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # NULL = all team members
    description = Column(Text, nullable=False)
    image_url = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    admin = relationship("User", foreign_keys=[admin_id])
    team_member = relationship("User", foreign_keys=[team_member_id])

class UserSession(Base):
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    login_time = Column(DateTime, default=datetime.utcnow)
    logout_time = Column(DateTime, nullable=True)
    date = Column(String(10), nullable=False)  # YYYY-MM-DD
    
    # Relationships
    user = relationship("User", back_populates="sessions")

# =================== HELPER FUNCTIONS ===================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return None
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
    except JWTError:
        return None
    
    user = db.query(User).filter(User.username == username).first()
    return user

def create_default_admin(db: Session):
    """Create default admin user if not exists"""
    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        # Create default admin with password: admin221108
        hashed_password = get_password_hash("admin221108")
        admin = User(
            name="Administrator",
            username="admin",
            email="admin@bitemebuddy.com",
            phone="+911234567890",
            password=hashed_password,
            address="Admin Headquarters",
            role="admin"
        )
        db.add(admin)
        db.commit()
        print("✅ Default admin user created: username='admin', password='admin221108'")
    return admin

# =================== MAIN ROUTES ===================

@app.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    """First page that users will see (Your existing page)"""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "title": "Welcome to Bite Me Buddy",
            "current_year": datetime.now().year
        }
    )

@app.get("/index2.html", response_class=HTMLResponse)
async def clock_page(request: Request):
    """Clock and registration/login page"""
    return templates.TemplateResponse(
        "index2.html",
        {
            "request": request,
            "title": "Bite Me Buddy - Order Now",
            "current_year": datetime.now().year
        }
    )

# =================== ADMIN LOGIN PAGE ===================

@app.get("/admin-login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """Special admin login page"""
    return templates.TemplateResponse(
        "admin_login.html",
        {
            "request": request,
            "title": "Admin Login - Bite Me Buddy"
        }
    )

@app.post("/admin-login")
async def admin_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Handle admin login with specific credentials"""
    
    # Special case for admin credentials
    if username == "admin" and password == "admin221108":
        # Check if admin exists in database
        admin = db.query(User).filter(User.username == "admin").first()
        
        if not admin:
            # Create admin user if not exists
            hashed_password = get_password_hash("admin221108")
            admin = User(
                name="Administrator",
                username="admin",
                email="admin@bitemebuddy.com",
                phone="+911234567890",
                password=hashed_password,
                address="Admin Headquarters",
                role="admin"
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
            print("✅ Admin user created automatically")
        
        # Create user session
        new_session = UserSession(
            user_id=admin.id,
            date=datetime.now().strftime("%Y-%m-%d")
        )
        db.add(new_session)
        db.commit()
        
        # Create access token
        access_token = create_access_token(
            data={"sub": admin.username, "role": admin.role}
        )
        
        # Redirect to admin dashboard
        response = RedirectResponse(url="/admin/dashboard", status_code=303)
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        return response
    
    # Check regular admin users
    user = db.query(User).filter(User.username == username).first()
    
    if not user or not verify_password(password, user.password):
        raise HTTPException(
            status_code=400,
            detail="Invalid username or password"
        )
    
    if user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )
    
    # Create user session
    new_session = UserSession(
        user_id=user.id,
        date=datetime.now().strftime("%Y-%-m-%d")
    )
    db.add(new_session)
    db.commit()
    
    # Create access token
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}
    )
    
    response = RedirectResponse(url="/admin/dashboard", status_code=303)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    
    return response

# =================== REGULAR LOGIN ===================

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Regular login page for customers and team members"""
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "title": "Login - Bite Me Buddy"
        }
    )

@app.post("/login")
async def login_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    user_type: str = Form("customer"),  # customer, team
    db: Session = Depends(get_db)
):
    """Handle regular user login (NOT for admin)"""
    
    # Prevent admin login through this route
    if username == "admin":
        return RedirectResponse(url="/admin-login", status_code=303)
    
    user = db.query(User).filter(User.username == username).first()
    
    if not user or not verify_password(password, user.password):
        raise HTTPException(
            status_code=400,
            detail="Invalid username or password"
        )
    
    # Check role based on user_type
    if user_type == "team" and user.role != "team_member":
        raise HTTPException(
            status_code=403,
            detail="Team member access required"
        )
    
    # Don't allow admin login here
    if user.role == "admin":
        return RedirectResponse(url="/admin-login", status_code=303)
    
    # Create user session
    new_session = UserSession(
        user_id=user.id,
        date=datetime.now().strftime("%Y-%m-%d")
    )
    db.add(new_session)
    db.commit()
    
    # Create access token
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}
    )
    
    # Redirect based on role
    if user.role == "team_member":
        redirect_url = "/team/dashboard"
    else:
        redirect_url = "/dashboard"
    
    response = RedirectResponse(url=redirect_url, status_code=303)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    
    return response

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Registration page"""
    return templates.TemplateResponse(
        "register.html",
        {
            "request": request,
            "title": "Register - Bite Me Buddy"
        }
    )

@app.post("/register")
async def register_user(
    request: Request,
    name: str = Form(...),
    username: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    password: str = Form(...),
    address: str = Form(...),
    db: Session = Depends(get_db)
):
    """Handle user registration"""
    # Don't allow 'admin' username for registration
    if username.lower() == "admin":
        raise HTTPException(
            status_code=400,
            detail="Username 'admin' is reserved"
        )
    
    # Check if user already exists
    existing_user = db.query(User).filter(
        (User.email == email) | (User.username == username)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email or username already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(password)
    new_user = User(
        name=name,
        username=username,
        email=email,
        phone=phone,
        password=hashed_password,
        address=address,
        role="customer"
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Create user session
    new_session = UserSession(
        user_id=new_user.id,
        date=datetime.now().strftime("%Y-%m-%d")
    )
    db.add(new_session)
    db.commit()
    
    # Create access token
    access_token = create_access_token(
        data={"sub": new_user.username, "role": new_user.role}
    )
    
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    
    return response

@app.get("/logout")
async def logout_user(request: Request, db: Session = Depends(get_db)):
    """Handle user logout"""
    user = get_current_user(request, db)
    if user:
        # Update session logout time
        session = db.query(UserSession).filter(
            UserSession.user_id == user.id,
            UserSession.logout_time.is_(None)
        ).order_by(UserSession.login_time.desc()).first()
        
        if session:
            session.logout_time = datetime.utcnow()
            db.commit()
    
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("access_token")
    return response

# =================== DASHBOARDS ===================

@app.get("/dashboard", response_class=HTMLResponse)
async def customer_dashboard(request: Request, db: Session = Depends(get_db)):
    """Customer dashboard page"""
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login")
    
    if user.role == "admin":
        return RedirectResponse(url="/admin/dashboard")
    
    # Get user's orders
    orders = db.query(Order).filter(
        Order.customer_id == user.id
    ).order_by(Order.created_at.desc()).limit(10).all()
    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "title": "Dashboard - Bite Me Buddy",
            "user": user,
            "orders": orders
        }
    )

@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    """Admin dashboard page"""
    user = get_current_user(request, db)
    if not user or user.role != "admin":
        return RedirectResponse(url="/admin-login")
    
    # Get statistics
    total_customers = db.query(User).filter(User.role == "customer").count()
    total_orders = db.query(Order).count()
    total_team_members = db.query(User).filter(User.role == "team_member").count()
    pending_orders = db.query(Order).filter(Order.status == "pending").count()
    
    # Get recent orders
    recent_orders = db.query(Order).order_by(Order.created_at.desc()).limit(10).all()
    
    # Get recent customers
    recent_customers = db.query(User).filter(User.role == "customer").order_by(User.created_at.desc()).limit(5).all()
    
    return templates.TemplateResponse(
        "admin_dashboard.html",
        {
            "request": request,
            "title": "Admin Dashboard - Bite Me Buddy",
            "user": user,
            "stats": {
                "customers": total_customers,
                "orders": total_orders,
                "team_members": total_team_members,
                "pending_orders": pending_orders
            },
            "recent_orders": recent_orders,
            "recent_customers": recent_customers
        }
    )

@app.get("/team/dashboard", response_class=HTMLResponse)
async def team_dashboard(request: Request, db: Session = Depends(get_db)):
    """Team member dashboard page"""
    user = get_current_user(request, db)
    if not user or user.role != "team_member":
        return RedirectResponse(url="/login?user_type=team")
    
    # Get assigned orders
    assigned_orders = db.query(Order).filter(
        Order.assigned_to == user.id,
        Order.status.in_(["confirmed", "preparing", "out_for_delivery"])
    ).order_by(Order.created_at.desc()).all()
    
    # Get today's plans
    today = datetime.now().strftime("%Y-%m-%d")
    plans = db.query(TeamMemberPlan).filter(
        (TeamMemberPlan.team_member_id == user.id) | 
        (TeamMemberPlan.team_member_id.is_(None))
    ).order_by(TeamMemberPlan.created_at.desc()).limit(5).all()
    
    return templates.TemplateResponse(
        "team_dashboard.html",
        {
            "request": request,
            "title": "Team Dashboard - Bite Me Buddy",
            "user": user,
            "assigned_orders": assigned_orders,
            "plans": plans
        }
    )

# =================== SERVICES ROUTES ===================

@app.get("/services", response_class=HTMLResponse)
async def services_page(request: Request, db: Session = Depends(get_db)):
    """Services listing page"""
    services = db.query(Service).all()
    return templates.TemplateResponse(
        "services.html",
        {
            "request": request,
            "title": "Our Services - Bite Me Buddy",
            "services": services
        }
    )

@app.get("/service/{service_id}/menu", response_class=HTMLResponse)
async def service_menu_page(request: Request, service_id: int, db: Session = Depends(get_db)):
    """Service menu page"""
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    menu_items = db.query(MenuItem).filter(MenuItem.service_id == service_id).all()
    
    return templates.TemplateResponse(
        "service_menu.html",
        {
            "request": request,
            "title": f"{service.name} Menu - Bite Me Buddy",
            "service": service,
            "menu_items": menu_items
        }
    )

# =================== ORDERS ROUTES ===================

@app.get("/cart", response_class=HTMLResponse)
async def cart_page(request: Request):
    """Shopping cart page"""
    return templates.TemplateResponse(
        "cart.html",
        {
            "request": request,
            "title": "My Cart - Bite Me Buddy"
        }
    )

@app.get("/myorders", response_class=HTMLResponse)
async def my_orders_page(request: Request, db: Session = Depends(get_db)):
    """Customer order history"""
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login")
    
    orders = db.query(Order).filter(
        Order.customer_id == user.id
    ).order_by(Order.created_at.desc()).all()
    
    return templates.TemplateResponse(
        "my_orders.html",
        {
            "request": request,
            "title": "My Orders - Bite Me Buddy",
            "user": user,
            "orders": orders
        }
    )

# =================== ADMIN MANAGEMENT ROUTES ===================

@app.get("/admin/services", response_class=HTMLResponse)
async def manage_services_page(request: Request, db: Session = Depends(get_db)):
    """Manage services page"""
    user = get_current_user(request, db)
    if not user or user.role != "admin":
        return RedirectResponse(url="/admin-login")
    
    services = db.query(Service).all()
    return templates.TemplateResponse(
        "manage_services.html",
        {
            "request": request,
            "title": "Manage Services - Bite Me Buddy",
            "services": services
        }
    )

@app.get("/admin/customers", response_class=HTMLResponse)
async def manage_customers_page(request: Request, db: Session = Depends(get_db)):
    """Manage customers page"""
    user = get_current_user(request, db)
    if not user or user.role != "admin":
        return RedirectResponse(url="/admin-login")
    
    customers = db.query(User).filter(User.role == "customer").all()
    return templates.TemplateResponse(
        "manage_customers.html",
        {
            "request": request,
            "title": "Manage Customers - Bite Me Buddy",
            "customers": customers
        }
    )

# =================== API ENDPOINTS ===================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Bite Me Buddy API",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/services")
async def get_services_api(db: Session = Depends(get_db)):
    """Get all services API"""
    services = db.query(Service).all()
    return {"services": services}

# =================== ERROR HANDLERS ===================

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Custom 404 page"""
    return templates.TemplateResponse(
        "404.html",
        {
            "request": request,
            "title": "Page Not Found - Bite Me Buddy"
        },
        status_code=404
    )

# =================== INITIALIZATION ===================

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    # Create database tables
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully")
    
    # Create default admin user
    db = SessionLocal()
    try:
        create_default_admin(db)
    finally:
        db.close()
    
    # Create uploads directory if not exists
    os.makedirs("static/uploads", exist_ok=True)
    os.makedirs("static/uploads/services", exist_ok=True)
    os.makedirs("static/uploads/menu", exist_ok=True)
    print("✅ Upload directories created")
    
    print("🚀 Bite Me Buddy API is ready!")
    print("📱 Home Page: http://localhost:8000")
    print("⏰ Clock Page: http://localhost:8000/index2.html")
    print("🔐 Admin Login: http://localhost:8000/admin-login")
    print("   Username: admin")
    print("   Password: admin221108")

# =================== MAIN ENTRY POINT ===================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
