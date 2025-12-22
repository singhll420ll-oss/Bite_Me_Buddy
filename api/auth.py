from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional

from database import get_db
from models import User, UserSession
from auth import AuthHandler, get_current_user, generate_otp, generate_reset_token
from email_service import email_service
from config import settings

router = APIRouter()

@router.post("/register")
async def register(
    request: Request,
    name: str = Form(...),
    username: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Register new user"""
    # Validation
    if password != confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    
    is_valid, message = AuthHandler.validate_password(password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=message)
    
    if not AuthHandler.validate_email(email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    
    if not AuthHandler.validate_phone(phone):
        raise HTTPException(status_code=400, detail="Invalid phone number")
    
    # Check if user exists
    existing_user = db.query(User).filter(
        (User.email == email) | (User.username == username)
    ).first()
    
    if existing_user:
        raise HTTPException(status_code=400, detail="Email or username already registered")
    
    # Create user
    hashed_password = AuthHandler.get_password_hash(password)
    verification_token = generate_reset_token()
    
    user = User(
        name=name,
        username=username,
        email=email,
        phone=phone,
        password_hash=hashed_password,
        role="customer",
        verification_token=verification_token
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Send welcome email
    email_service.send_welcome_email(user.email, user.name)
    
    return {
        "success": True,
        "message": "Registration successful. Please verify your email.",
        "user_id": user.id
    }

@router.post("/login")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Login user and return tokens"""
    user = db.query(User).filter(
        (User.username == form_data.username) | (User.email == form_data.username),
        User.is_active == True
    ).first()
    
    if not user or not AuthHandler.verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create user session
    session_token = AuthHandler.create_session_token()
    session = UserSession(
        user_id=user.id,
        session_token=session_token,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
        device_type="web",
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    
    db.add(session)
    
    # Update user last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    # Create tokens
    access_token = AuthHandler.create_access_token(
        data={
            "sub": user.username,
            "role": user.role,
            "user_id": user.id,
            "session_token": session_token
        }
    )
    
    refresh_token = AuthHandler.create_refresh_token(
        data={
            "sub": user.username,
            "session_token": session_token
        }
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "profile_image": user.profile_image
        }
    }

@router.post("/logout")
async def logout(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Logout user"""
    # Get session token from request
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        payload = AuthHandler.decode_token(token)
        session_token = payload.get("session_token") if payload else None
        
        if session_token:
            session = db.query(UserSession).filter(
                UserSession.session_token == session_token,
                UserSession.user_id == user.id,
                UserSession.is_active == True
            ).first()
            
            if session:
                session.is_active = False
                session.logout_time = datetime.utcnow()
                db.commit()
    
    return {"success": True, "message": "Logged out successfully"}

@router.post("/refresh")
async def refresh_token(
    request: Request,
    db: Session = Depends(get_db)
):
    """Refresh access token using refresh token"""
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            refresh_token = auth_header[7:]
    
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token required")
    
    # Decode refresh token
    payload = AuthHandler.decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    username = payload.get("sub")
    session_token = payload.get("session_token")
    
    # Verify session
    session = db.query(UserSession).filter(
        UserSession.session_token == session_token,
        UserSession.is_active == True
    ).first()
    
    if not session:
        raise HTTPException(status_code=401, detail="Session expired")
    
    # Get user
    user = db.query(User).filter(
        User.username == username,
        User.is_active == True
    ).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    # Create new access token
    access_token = AuthHandler.create_access_token(
        data={
            "sub": user.username,
            "role": user.role,
            "user_id": user.id,
            "session_token": session_token
        }
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.post("/forgot-password")
async def forgot_password(
    email: str = Form(...),
    db: Session = Depends(get_db)
):
    """Request password reset"""
    user = db.query(User).filter(
        User.email == email,
        User.is_active == True
    ).first()
    
    if user:
        reset_token = generate_reset_token()
        user.reset_token = reset_token
        db.commit()
        
        # Send reset email
        email_service.send_password_reset_email(user.email, reset_token, user.name)
    
    # Always return success to prevent email enumeration
    return {
        "success": True,
        "message": "If your email exists, you will receive a password reset link"
    }

@router.post("/reset-password")
async def reset_password(
    token: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Reset password using token"""
    if new_password != confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    
    is_valid, message = AuthHandler.validate_password(new_password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=message)
    
    user = db.query(User).filter(
        User.reset_token == token,
        User.is_active == True
    ).first()
    
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    
    # Update password
    user.password_hash = AuthHandler.get_password_hash(new_password)
    user.reset_token = None
    db.commit()
    
    return {
        "success": True,
        "message": "Password reset successfully"
    }

@router.get("/me")
async def get_current_user_profile(
    user: User = Depends(get_current_user)
):
    """Get current user profile"""
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "role": user.role,
        "profile_image": user.profile_image,
        "is_verified": user.is_verified
      }
