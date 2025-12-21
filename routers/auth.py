"""
Authentication Router for Bite Me Buddy - MOBILE EDITION
Handles user registration, login with mobile number and password
"""

from fastapi import APIRouter, Depends, Request, Response, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging
import json
import traceback
import jwt
from typing import Dict, Any, Optional

from database import get_db, get_sync_db
from schemas.schemas import (
    UserCreate, UserLogin, Token, UserResponse, 
    RegisterResponse, LoginResponse, UserProfileUpdate,
    PasswordChange, MobileUpdate
)
from crud.user import (
    create_user, get_user_by_mobile, get_user_by_id,
    authenticate_user, update_user_profile, change_user_password,
    update_user_mobile, get_user_by_email
)
from crud.session import create_user_session, update_session_logout_by_user
from core.security import (
    verify_password, create_access_token, 
    get_password_hash, get_current_user
)
from core.config import settings

# Initialize router and templates
router = APIRouter(tags=["authentication"])
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger(__name__)

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# ========== TEMPLATE ROUTES ==========

@router.get("/", response_class=HTMLResponse)
async def home_page(request: Request) -> HTMLResponse:
    """Render home page"""
    return templates.TemplateResponse("index.html", {"request": request})

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request) -> HTMLResponse:
    """Render mobile registration page"""
    return templates.TemplateResponse("auth/register.html", {"request": request})

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    """Render mobile login page"""
    return templates.TemplateResponse("auth/login.html", {"request": request})

@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request) -> HTMLResponse:
    """Render forgot password page"""
    return templates.TemplateResponse("auth/forgot_password.html", {"request": request})

@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request) -> HTMLResponse:
    """Render user profile page"""
    return templates.TemplateResponse("auth/profile.html", {"request": request})

# ========== MOBILE REGISTRATION API ==========

@router.post("/register", response_model=RegisterResponse)
async def register_mobile_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    request: Request = None
):
    """
    Register a new user with mobile number and password
    """
    try:
        logger.info(f"Mobile registration attempt: {user_data.mobile}")
        
        # Check if user already exists
        existing_user = await get_user_by_mobile(db, user_data.mobile)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mobile number already registered"
            )
        
        # Check if email is provided and unique
        if user_data.email:
            existing_email_user = await get_user_by_email(db, user_data.email)
            if existing_email_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
        
        # Create user
        user = await create_user(db, user_data)
        
        # Create session
        session = None
        try:
            session = await create_user_session(
                db,
                user.id,
                request.client.host if request and request.client else None,
                request.headers.get("user-agent", "Mobile Registration") if request else None
            )
        except Exception as e:
            logger.warning(f"Could not create session: {e}")
        
        # Create access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.mobile, "id": user.id, "role": user.role},
            expires_delta=access_token_expires
        )
        
        # Create token response
        token = Token(
            access_token=access_token,
            token_type="bearer",
            user=UserResponse.from_orm(user)
        )
        
        return RegisterResponse(
            message="Registration successful!",
            user=UserResponse.from_orm(user),
            token=token
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during registration"
        )

# ========== MOBILE LOGIN API ==========

@router.post("/login", response_model=LoginResponse)
async def login_mobile_user(
    user_login: UserLogin,
    db: AsyncSession = Depends(get_db),
    request: Request = None
):
    """
    Authenticate user with mobile number and password
    """
    try:
        logger.info(f"Mobile login attempt: {user_login.mobile}")
        
        # Authenticate user
        user = await authenticate_user(db, user_login.mobile, user_login.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid mobile number or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is inactive"
            )
        
        # Create session
        session = await create_user_session(
            db,
            user.id,
            request.client.host if request and request.client else None,
            request.headers.get("user-agent", "Mobile Login") if request else None
        )
        
        # Create access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.mobile, "id": user.id, "role": user.role},
            expires_delta=access_token_expires
        )
        
        # Create token response
        token = Token(
            access_token=access_token,
            token_type="bearer",
            user=UserResponse.from_orm(user)
        )
        
        return LoginResponse(
            message="Login successful",
            token=token
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during login"
        )

# ========== TOKEN-BASED LOGIN (FOR FORM) ==========

@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    OAuth2 compatible token login (for compatibility)
    """
    # For mobile auth, username is mobile number
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.mobile, "id": user.id, "role": user.role},
        expires_delta=access_token_expires
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.from_orm(user)
    )

# ========== PROFILE MANAGEMENT ==========

@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current authenticated user profile"""
    user = await get_user_by_id(db, current_user.id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return UserResponse.from_orm(user)

@router.put("/profile", response_model=UserResponse)
async def update_profile(
    profile_data: UserProfileUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user profile"""
    user = await update_user_profile(db, current_user.id, profile_data)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return UserResponse.from_orm(user)

@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Change user password"""
    success = await change_user_password(db, current_user.id, password_data)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    return {"message": "Password changed successfully"}

@router.post("/change-mobile")
async def change_mobile_number(
    mobile_data: MobileUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Change mobile number"""
    try:
        success = await update_user_mobile(
            db, current_user.id, mobile_data.new_mobile, mobile_data.password
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password is incorrect or mobile number already exists"
            )
        return {"message": "Mobile number updated successfully"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# ========== LOGOUT ==========

@router.post("/logout")
async def logout(
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Logout user and clear all sessions"""
    await update_session_logout_by_user(db, current_user.id)
    return {"message": "Logout successful"}

# ========== CHECK MOBILE AVAILABILITY ==========

@router.get("/check-mobile/{mobile}")
async def check_mobile_availability(
    mobile: str,
    db: AsyncSession = Depends(get_db)
):
    """Check if mobile number is available for registration"""
    user = await get_user_by_mobile(db, mobile)
    return {"available": user is None}

# ========== SIMPLE REGISTRATION (FOR TESTING) ==========

@router.post("/simple-register")
async def simple_register_endpoint(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Simple registration endpoint for testing
    """
    try:
        data = await request.json()
        
        # Validate required fields
        if not data.get("mobile") or not data.get("password"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Mobile and password are required"
            )
        
        # Create user data
        user_data = UserCreate(
            mobile=data["mobile"],
            password=data["password"],
            name=data.get("name"),
            email=data.get("email"),
            address=data.get("address")
        )
        
        # Create user
        user = await create_user(db, user_data)
        
        # Create token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.mobile, "id": user.id, "role": user.role},
            expires_delta=access_token_expires
        )
        
        return {
            "success": True,
            "message": "Registration successful",
            "user": {
                "id": user.id,
                "mobile": user.mobile,
                "name": user.name
            },
            "access_token": access_token,
            "token_type": "bearer"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Simple register error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

# ========== HEALTH CHECK ==========

@router.get("/health")
async def auth_health_check():
    """Authentication service health check"""
    return {
        "status": "healthy",
        "service": "mobile-authentication",
        "endpoints": [
            "/register - Mobile registration",
            "/login - Mobile login", 
            "/me - Get profile",
            "/logout - Logout"
        ]
    }

# ========== HTML TEMPLATE REDIRECTS ==========

@router.get("/service.html")
async def service_page_redirect():
    """Redirect from old service.html"""
    return RedirectResponse(url="/services.html", status_code=307)

@router.get("/services.html", response_class=HTMLResponse)
async def services_page(request: Request) -> HTMLResponse:
    """Render services page"""
    return templates.TemplateResponse("services.html", {"request": request})

@router.get("/admin-login", response_class=HTMLResponse)
async def admin_login_page(request: Request) -> HTMLResponse:
    """Render admin login page"""
    try:
        return templates.TemplateResponse("admin_login.html", {"request": request})
    except:
        return templates.TemplateResponse("auth/login.html", {"request": request})

# ========== ERROR HANDLING ==========

@router.get("/test-redirect")
async def test_redirect():
    """Test redirect endpoint"""
    return {
        "mobile_auth": "active",
        "endpoints": {
            "register": "/auth/register",
            "login": "/auth/login",
            "profile": "/auth/me"
        }
    }