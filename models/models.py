
# File: models.py
from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, Text, ForeignKey, Enum, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()

class UserRole(str, enum.Enum):
    CUSTOMER = "customer"
    TEAM_MEMBER = "team_member"
    ADMIN = "admin"

class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PREPARING = "preparing"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

class PaymentMethod(str, enum.Enum):
    CASH = "cash"
    CARD = "card"
    UPI = "upi"

class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"

class NotificationType(str, enum.Enum):
    ORDER_CREATED = "order_created"
    ORDER_UPDATED = "order_updated"
    ORDER_DELIVERED = "order_delivered"
    PROMOTIONAL = "promotional"
    SYSTEM = "system"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    phone = Column(String(20), nullable=False)
    password_hash = Column(String(255), nullable=False)
    address = Column(Text)
    city = Column(String(50))
    state = Column(String(50))
    pincode = Column(String(10))
    profile_image = Column(String(255), default="/static/images/default-avatar.png")
    role = Column(String(20), default=UserRole.CUSTOMER)
    is_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    verification_token = Column(String(100))
    reset_token = Column(String(100))
    last_login = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    orders = relationship("Order", back_populates="customer", foreign_keys="Order.customer_id")
    assigned_orders = relationship("Order", back_populates="team_member", foreign_keys="Order.assigned_to")
    reviews = relationship("Review", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    sessions = relationship("UserSession", back_populates="user")
    payments = relationship("Payment", back_populates="user")
    addresses = relationship("UserAddress", back_populates="user")

class UserAddress(Base):
    __tablename__ = "user_addresses"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    label = Column(String(50), nullable=False)  # Home, Office, etc.
    address_line1 = Column(String(200), nullable=False)
    address_line2 = Column(String(200))
    city = Column(String(50), nullable=False)
    state = Column(String(50), nullable=False)
    pincode = Column(String(10), nullable=False)
    is_default = Column(Boolean, default=False)
    latitude = Column(Float)
    longitude = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="addresses")
    orders = relationship("Order", back_populates="delivery_address")

class Service(Base):
    __tablename__ = "services"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    slug = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(Text)
    short_description = Column(String(200))
    image_url = Column(String(255), default="/static/images/default-service.jpg")
    banner_image = Column(String(255))
    rating = Column(Float, default=0.0)
    total_reviews = Column(Integer, default=0)
    preparation_time = Column(Integer, default=30)  # in minutes
    delivery_fee = Column(Float, default=20.0)
    min_order_amount = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    is_featured = Column(Boolean, default=False)
    opening_time = Column(String(5), default="09:00")  # HH:MM format
    closing_time = Column(String(5), default="23:00")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    menu_items = relationship("MenuItem", back_populates="service", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="service")
    reviews = relationship("Review", back_populates="service")
    categories = relationship("Category", secondary="service_categories", back_populates="services")

class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True)
    slug = Column(String(50), nullable=False, unique=True, index=True)
    description = Column(Text)
    image_url = Column(String(255))
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    parent = relationship("Category", remote_side=[id], back_populates="children")
    children = relationship("Category", back_populates="parent")
    services = relationship("Service", secondary="service_categories", back_populates="categories")
    menu_items = relationship("MenuItem", back_populates="category")

class ServiceCategory(Base):
    __tablename__ = "service_categories"
    
    service_id = Column(Integer, ForeignKey("services.id"), primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.id"), primary_key=True)

class MenuItem(Base):
    __tablename__ = "menu_items"
    
    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(Text)
    short_description = Column(String(200))
    price = Column(Float, nullable=False)
    discounted_price = Column(Float)
    image_url = Column(String(255), default="/static/images/default-food.jpg")
    ingredients = Column(Text)
    is_vegetarian = Column(Boolean, default=True)
    is_spicy = Column(Boolean, default=False)
    is_available = Column(Boolean, default=True)
    is_featured = Column(Boolean, default=False)
    preparation_time = Column(Integer, default=15)  # in minutes
    calories = Column(Integer)
    display_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    service = relationship("Service", back_populates="menu_items")
    category = relationship("Category", back_populates="menu_items")
    order_items = relationship("OrderItem", back_populates="menu_item")
    reviews = relationship("Review", back_populates="menu_item")

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(20), unique=True, index=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    delivery_address_id = Column(Integer, ForeignKey("user_addresses.id"), nullable=True)
    
    # Order details
    subtotal = Column(Float, nullable=False)
    tax_amount = Column(Float, default=0.0)
    delivery_charge = Column(Float, default=0.0)
    discount_amount = Column(Float, default=0.0)
    total_amount = Column(Float, nullable=False)
    
    # Delivery details
    delivery_instructions = Column(Text)
    estimated_delivery_time = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    
    # Status
    status = Column(String(20), default=OrderStatus.PENDING)
    status_history = Column(JSON)  # Store status change history
    
    # Assignment
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # OTP for delivery verification
    delivery_otp = Column(String(6))
    otp_expiry = Column(DateTime)
    
    # Payment
    payment_method = Column(String(20), default=PaymentMethod.CASH)
    payment_status = Column(String(20), default=PaymentStatus.PENDING)
    payment_id = Column(String(100))
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    customer = relationship("User", foreign_keys=[customer_id], back_populates="orders")
    service = relationship("Service", back_populates="orders")
    team_member = relationship("User", foreign_keys=[assigned_to], back_populates="assigned_orders")
    delivery_address = relationship("UserAddress", back_populates="orders")
    order_items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="order")
    reviews = relationship("Review", back_populates="order")

class OrderItem(Base):
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    menu_item_id = Column(Integer, ForeignKey("menu_items.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    price_at_time = Column(Float, nullable=False)
    special_instructions = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    order = relationship("Order", back_populates="order_items")
    menu_item = relationship("MenuItem", back_populates="order_items")

class Review(Base):
    __tablename__ = "reviews"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    menu_item_id = Column(Integer, ForeignKey("menu_items.id"), nullable=True)
    
    rating = Column(Integer, nullable=False)  # 1-5
    comment = Column(Text)
    is_verified_purchase = Column(Boolean, default=True)
    is_approved = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="reviews")
    order = relationship("Order", back_populates="reviews")
    service = relationship("Service", back_populates="reviews")
    menu_item = relationship("MenuItem", back_populates="reviews")

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Payment details
    payment_gateway = Column(String(50))  # stripe, razorpay, etc.
    payment_method = Column(String(20), default=PaymentMethod.CASH)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="INR")
    
    # Gateway response
    gateway_transaction_id = Column(String(100))
    gateway_response = Column(JSON)
    
    # Status
    status = Column(String(20), default=PaymentStatus.PENDING)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    order = relationship("Order", back_populates="payments")
    user = relationship("User", back_populates="payments")

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Notification details
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(String(50), default=NotificationType.SYSTEM)
    data = Column(JSON)  # Additional data for deep linking
    
    # Status
    is_read = Column(Boolean, default=False)
    is_sent = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    read_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="notifications")

class UserSession(Base):
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_token = Column(String(255), unique=True, nullable=False)
    
    # Session details
    ip_address = Column(String(45))
    user_agent = Column(Text)
    device_type = Column(String(50))  # mobile, desktop, tablet
    browser = Column(String(50))
    os = Column(String(50))
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    login_time = Column(DateTime, default=datetime.utcnow)
    logout_time = Column(DateTime, nullable=True)
    last_activity = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="sessions")

class TeamMemberPlan(Base):
    __tablename__ = "team_member_plans"
    
    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    team_member_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Plan details
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    plan_date = Column(String(10), nullable=False)  # YYYY-MM-DD
    start_time = Column(String(5))  # HH:MM
    end_time = Column(String(5))  # HH:MM
    
    # Priority and status
    priority = Column(String(20), default="medium")
    status = Column(String(20), default="pending")
    
    # Additional
    image_url = Column(String(255))
    location = Column(String(200))
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    admin = relationship("User", foreign_keys=[admin_id])
    team_member = relationship("User", foreign_keys=[team_member_id])

class DeliveryZone(Base):
    __tablename__ = "delivery_zones"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    
    # Zone coordinates (simplified)
    polygon_coordinates = Column(JSON)  # List of [lat, lng] pairs
    
    # Delivery charges
    base_delivery_charge = Column(Float, default=20.0)
    minimum_order_amount = Column(Float, default=0.0)
    delivery_time_minutes = Column(Integer, default=45)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Coupon(Base):
    __tablename__ = "coupons"
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    
    # Discount details
    discount_type = Column(String(20), default="percentage")  # percentage or fixed
    discount_value = Column(Float, nullable=False)
    max_discount_amount = Column(Float)
    min_order_amount = Column(Float, default=0.0)
    
    # Usage limits
    usage_limit = Column(Integer, nullable=True)
    used_count = Column(Integer, default=0)
    per_user_limit = Column(Integer, default=1)
    
    # Validity
    valid_from = Column(DateTime, nullable=False)
    valid_until = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    
    # Applicability
    applicable_services = Column(JSON)  # List of service IDs
    applicable_categories = Column(JSON)  # List of category IDs
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Cart(Base):
    __tablename__ = "carts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    
    # Cart data
    items = Column(JSON)  # Store cart items as JSON
    total_amount = Column(Float, default=0.0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User")
    service = relationship("Service")
