from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime, date
from enum import Enum

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

# Base Schemas
class UserBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    phone: str = Field(..., min_length=10, max_length=20)
    address: Optional[str] = None

# ✅ UPDATED: UserCreate schema with all required fields
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    full_name: str = Field(..., min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    phone: str = Field(..., min_length=10, max_length=20)
    address: str = Field(..., min_length=5)
    password: str = Field(..., min_length=6)
    role: UserRole = UserRole.CUSTOMER

class UserLogin(BaseModel):
    username: str
    password: str

# ✅ UPDATED: UserResponse schema
class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str
    email: Optional[str]
    phone: str
    address: str
    role: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class UserDetailResponse(UserResponse):
    total_orders: int = 0
    total_spent: float = 0
    last_order_date: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Service Schemas
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
    
    class Config:
        from_attributes = True

# Menu Item Schemas
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
    
    class Config:
        from_attributes = True

# Order Schemas
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
    
    class Config:
        from_attributes = True

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
    
    class Config:
        from_attributes = True

class OrderUpdate(BaseModel):
    status: Optional[OrderStatus] = None
    assigned_to: Optional[int] = None

class OTPVerify(BaseModel):
    order_id: int
    otp: str = Field(..., min_length=4, max_length=4)

# Team Member Plan Schemas
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
    
    class Config:
        from_attributes = True

# Session Schemas
class UserSessionResponse(BaseModel):
    id: int
    user_id: int
    login_time: datetime
    logout_time: Optional[datetime]
    date: date
    duration_minutes: Optional[float] = None
    
    class Config:
        from_attributes = True

# Admin Report Schemas
class OnlineTimeReport(BaseModel):
    user_id: int
    username: str
    name: str
    role: str
    total_sessions: int
    total_time_minutes: float
    avg_session_minutes: float
    last_login: Optional[datetime]
    
    class Config:
        from_attributes = True

# Token Response
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# File Upload Response
class FileUploadResponse(BaseModel):
    filename: str
    url: str
    size: int