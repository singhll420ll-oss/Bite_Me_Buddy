from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta
import logging
import json

from database import get_db
from schemas.schemas import UserCreate, UserLogin, TokenResponse
from crud.user import create_user, get_user_by_username
from crud.session import create_user_session, update_user_session_logout
from core.security import verify_password, create_access_token, get_current_user
from core.config import settings

router = APIRouter(tags=["authentication"])
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger(__name__)

@router.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    """Home page with clock and buttons"""
    return templates.TemplateResponse("index.html", {"request": request})

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Registration page"""
    return templates.TemplateResponse("register.html", {"request": request})

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page"""
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/api/register")
async def register(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Register new user - FIXED VERSION"""
    
    try:
        # DEBUG: Log the request
        logger.info(f"Registration attempt from: {request.client.host if request.client else 'Unknown'}")
        
        # Get raw JSON data
        try:
            raw_data = await request.json()
            logger.info(f"Received registration data: {raw_data}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            return JSONResponse(
                status_code=422,
                content={
                    "detail": "Invalid JSON format",
                    "error": str(e)
                }
            )
        
        # Check required fields manually first
        required_fields = ["username", "email", "password"]
        missing_fields = [field for field in required_fields if field not in raw_data]
        
        if missing_fields:
            logger.warning(f"Missing fields: {missing_fields}")
            return JSONResponse(
                status_code=422,
                content={
                    "detail": f"Missing required fields: {', '.join(missing_fields)}",
                    "missing_fields": missing_fields
                }
            )
        
        # Now use Pydantic model for validation
        try:
            user_data = UserCreate(**raw_data)
            logger.info(f"Validated user data: {user_data}")
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return JSONResponse(
                status_code=422,
                content={
                    "detail": "Validation failed",
                    "error": str(e)
                }
            )
        
        # Check if username already exists
        existing_user = await get_user_by_username(db, user_data.username)
        if existing_user:
            logger.warning(f"Username already exists: {user_data.username}")
            return JSONResponse(
                status_code=400,
                content={
                    "detail": "Username already registered",
                    "suggestion": "Please choose a different username"
                }
            )
        
        # Create user
        user = await create_user(db, user_data)
        logger.info(f"User created successfully: {user.username}")
        
        # Create session
        session = await create_user_session(
            db,
            user.id,
            request.client.host if request.client else None,
            request.headers.get("user-agent")
        )
        logger.info(f"Session created: {session.id}")
        
        # Create access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id), "role": user.role},
            expires_delta=access_token_expires
        )
        
        # OPTION 1: Return JSON response (Recommended for API)
        response_data = {
            "success": True,
            "message": "User registered successfully",
            "user": {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "role": user.role
            },
            "redirect_url": "/services",
            "session_id": str(session.id)
        }
        
        response = JSONResponse(content=response_data, status_code=201)
        
        # Set cookies
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=not settings.DEBUG,
            samesite="lax",
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        response.set_cookie(
            key="user_id",
            value=str(user.id),
            httponly=False,
            secure=not settings.DEBUG,
            samesite="lax"
        )
        response.set_cookie(
            key="session_id",
            value=str(session.id),
            httponly=True,
            secure=not settings.DEBUG,
            samesite="lax"
        )
        
        return response
        
        # OPTION 2: Uncomment below if you want HTML redirect instead of JSON
        """
        # Create HTML redirect response
        response = RedirectResponse(url="/services", status_code=303)
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=not settings.DEBUG,
            samesite="lax",
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        response.set_cookie(
            key="user_id",
            value=str(user.id),
            httponly=False,
            secure=not settings.DEBUG,
            samesite="lax"
        )
        response.set_cookie(
            key="session_id",
            value=str(session.id),
            httponly=True,
            secure=not settings.DEBUG,
            samesite="lax"
        )
        return response
        """
        
    except Exception as e:
        logger.error(f"Unexpected error in registration: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "error": str(e)
            }
        )

@router.post("/api/login")
async def login(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Login user - FIXED VERSION"""
    
    try:
        # Get raw data
        raw_data = await request.json()
        logger.info(f"Login attempt data: {raw_data}")
        
        # Manual validation
        if "username" not in raw_data or "password" not in raw_data:
            return JSONResponse(
                status_code=422,
                content={
                    "detail": "Username and password are required"
                }
            )
        
        # Use Pydantic model
        login_data = UserLogin(**raw_data)
        
        # Get user
        user = await get_user_by_username(db, login_data.username)
        if not user or not user.is_active:
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Invalid credentials"
                }
            )
        
        # Verify password
        if not verify_password(login_data.password, user.hashed_password):
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Invalid credentials"
                }
            )
        
        # Create session
        session = await create_user_session(
            db,
            user.id,
            request.client.host if request.client else None,
            request.headers.get("user-agent")
        )
        
        # Create access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id), "role": user.role},
            expires_delta=access_token_expires
        )
        
        # Determine redirect URL based on role
        if user.role == "admin":
            redirect_url = "/admin/dashboard"
        elif user.role == "team_member":
            redirect_url = "/team/dashboard"
        else:
            redirect_url = "/services"
        
        # Return JSON response
        response_data = {
            "success": True,
            "message": "Login successful",
            "user": {
                "id": str(user.id),
                "username": user.username,
                "role": user.role
            },
            "redirect_url": redirect_url,
            "session_id": str(session.id)
        }
        
        response = JSONResponse(content=response_data, status_code=200)
        
        # Set cookies
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=not settings.DEBUG,
            samesite="lax",
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        response.set_cookie(
            key="user_id",
            value=str(user.id),
            httponly=False,
            secure=not settings.DEBUG,
            samesite="lax"
        )
        response.set_cookie(
            key="session_id",
            value=str(session.id),
            httponly=True,
            secure=not settings.DEBUG,
            samesite="lax"
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "error": str(e)
            }
        )

@router.get("/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Logout user"""
    
    # Get session ID from cookie
    session_id = request.cookies.get("session_id")
    if session_id:
        try:
            await update_user_session_logout(db, int(session_id))
        except:
            pass
    
    # Clear cookies and redirect
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("access_token")
    response.delete_cookie("user_id")
    response.delete_cookie("session_id")
    
    return response

@router.get("/admin-login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """Admin login page (accessed via secret clock)"""
    return templates.TemplateResponse("admin_login.html", {"request": request})

# Debug endpoint - Test registration
@router.post("/api/test-register")
async def test_register(request: Request):
    """Test registration endpoint"""
    try:
        data = await request.json()
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Test endpoint working",
                "received_data": data,
                "note": "This is just for testing validation"
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={
                "error": str(e),
                "received_body": await request.body()
            }
        )