from pydantic import BaseModel, EmailStr, Field, validator, ConfigDict
from typing import Optional, List
from datetime import datetime, date
from enum import Enum
import re

class UserRole(str, Enum):
    CUSTOMER = "customer"
    TEAM_MEMBER = "team_member"
    ADMIN = "admin"

class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PREPARING = "preparing"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

# ========== MOBILE AUTHENTICATION SCHEMAS ==========

class MobileAuthBase(BaseModel):
    """Base schema for mobile authentication"""
    @validator('mobile')
    def validate_mobile(cls, v):
        """Validate mobile number format"""
        if not v:
            raise ValueError('Mobile number is required')
        
        # Remove any spaces or special characters
        v = re.sub(r'\D', '', v)
        
        # Check if it's 10 digits
        if len(v) != 10:
            raise ValueError('Mobile number must be 10 digits')
        
        # Check if it starts with valid Indian prefix
        if not v.startswith(('6', '7', '8', '9')):
            raise ValueError('Mobile number must start with 6, 7, 8, or 9')
        
        return v

# ✅ UPDATED: UserCreate schema for mobile registration
class UserCreate(MobileAuthBase):
    mobile: str = Field(..., min_length=10, max_length=10, description="10-digit mobile number")
    password: str = Field(..., min_length=6, description="Password (min 6 characters)")
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    role: UserRole = UserRole.CUSTOMER
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "mobile": "9876543210",
                "password": "securepassword123",
                "name": "John Doe",
                "email": "john@example.com",
                "address": "123 Main St, City",
                "role": "customer"
            }
        }
    )

# ✅ NEW: Mobile Login Schema
class UserLogin(MobileAuthBase):
    mobile: str = Field(..., min_length=10, max_length=10, description="10-digit mobile number")
    password: str = Field(..., description="Password")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "mobile": "9876543210",
                "password": "securepassword123"
            }
        }
    )

# ✅ NEW: Mobile Verification Schema
class MobileVerify(BaseModel):
    mobile: str = Field(..., min_length=10, max_length=10)
    otp: str = Field(..., min_length=4, max_length=6)

# ✅ UPDATED: UserResponse schema with mobile
class UserResponse(BaseModel):
    id: int
    mobile: str
    name: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)

# ✅ UPDATED: UserDetailResponse with mobile
class UserDetailResponse(UserResponse):
    total_orders: int = 0
    total_spent: float = 0.0
    last_order_date: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)

# ✅ NEW: User Profile Update Schema
class UserProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Updated Name",
                "email": "updated@example.com",
                "address": "New Address, City"
            }
        }
    )

# ✅ NEW: Password Change Schema
class PasswordChange(BaseModel):
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=6, description="New password (min 6 characters)")
    
    @validator('new_password')
    def validate_new_password(cls, v):
        if len(v) < 6:
            raise ValueError('New password must be at least 6 characters long')
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "current_password": "oldpassword123",
                "new_password": "newpassword456"
            }
        }
    )

# ✅ NEW: Mobile Update Schema
class MobileUpdate(MobileAuthBase):
    new_mobile: str = Field(..., min_length=10, max_length=10)
    password: str = Field(..., description="Current password for verification")

# ========== TOKEN SCHEMAS ==========

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class TokenData(BaseModel):
    mobile: Optional[str] = None
    user_id: Optional[int] = None

# ========== EXISTING SCHEMAS (UPDATED) ==========

class ServiceBase(BaseModel):
    name: str = Field(..., max_length=100)
    description: Optional[str] = None

class ServiceCreate(ServiceBase):
    pass

class ServiceResponse(ServiceBase):
    id: int
    image_url: Optional[str]
    is_active: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class MenuItemBase(BaseModel):
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    price: float = Field(..., gt=0)
    
    @validator('price')
    def validate_price(cls, v):
        if v <= 0:
            raise ValueError('Price must be greater than 0')
        return round(v, 2)

class MenuItemCreate(MenuItemBase):
    service_id: int

class MenuItemResponse(MenuItemBase):
    id: int
    service_id: int
    image_url: Optional[str]
    is_available: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class OrderItemCreate(BaseModel):
    menu_item_id: int
    quantity: int = Field(..., ge=1)

class OrderCreate(BaseModel):
    service_id: int
    address: str
    phone: str
    special_instructions: Optional[str] = None
    items: List[OrderItemCreate]

class OrderItemResponse(BaseModel):
    id: int
    menu_item_name: str
    quantity: int
    price_at_order: float
    
    model_config = ConfigDict(from_attributes=True)

class OrderResponse(BaseModel):
    id: int
    order_number: str
    customer_id: int
    service_id: int
    total_amount: float
    address: str
    phone: str
    special_instructions: Optional[str]
    status: str
    assigned_to: Optional[int]
    created_at: datetime
    order_items: List[OrderItemResponse]
    
    model_config = ConfigDict(from_attributes=True)

class OrderUpdate(BaseModel):
    status: Optional[OrderStatus] = None
    assigned_to: Optional[int] = None

class OTPVerify(BaseModel):
    order_id: int
    otp: str = Field(..., min_length=4, max_length=4)

class TeamMemberPlanCreate(BaseModel):
    team_member_id: int
    description: str
    image_url: Optional[str] = None

class TeamMemberPlanResponse(BaseModel):
    id: int
    admin_id: int
    team_member_id: int
    description: str
    image_url: Optional[str]
    is_read: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class UserSessionResponse(BaseModel):
    id: int
    user_id: int
    login_time: datetime
    logout_time: Optional[datetime]
    date: date
    duration_minutes: Optional[float] = None
    
    model_config = ConfigDict(from_attributes=True)

class OnlineTimeReport(BaseModel):
    user_id: int
    mobile: str
    name: Optional[str]
    role: str
    total_sessions: int
    total_time_minutes: float
    avg_session_minutes: float
    last_login: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)

class FileUploadResponse(BaseModel):
    filename: str
    url: str
    size: int

# ========== AUTH RESPONSE SCHEMAS ==========

class RegisterResponse(BaseModel):
    message: str
    user: UserResponse
    token: Token

class LoginResponse(BaseModel):
    message: str = "Login successful"
    token: Token

class LogoutResponse(BaseModel):
    message: str = "Logout successful"

# ========== ERROR RESPONSE SCHEMAS ==========

class ErrorResponse(BaseModel):
    detail: str

class ValidationError(BaseModel):
    loc: List[str]
    msg: str
    type: str

class HTTPValidationError(BaseModel):
    detail: List[ValidationError]