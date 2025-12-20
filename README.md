# Bite Me Buddy - Food Ordering System

A production-ready, high-performance, mobile-friendly food ordering website for the "Bite Me Buddy" restaurant. Built with FastAPI (async), PostgreSQL, and modern web technologies.

## Features

### 🏠 Home Page
- Clean, simple design with real-time digital clock (IST, 12-hour format)
- Three large touch-friendly buttons:
  1. New Registration
  2. Already Registered (Customer Login)
  3. Team Member Login

### 🔐 Secret Admin Access (Hidden Feature)
- **15-second long press + 5 taps** on the clock to enter edit mode
- No visual hints, timer bars, or text indicators
- Set time to 3:43 (AM/PM) and save to access `/admin-login`
- Completely hidden - normal users won't know it exists

### 👥 Customer Flow
- Registration with session tracking (login_time, logout_time)
- Browse services and menus
- Add items to cart
- Place orders with address/phone/notes
- View order history
- OTP verification for delivery

### 👨‍🍳 Team Member Flow
- View assigned orders
- See complete item lists (scrollable for 10-15+ items)
- Confirm delivery with OTP verification
- View "Today's Plan" from admin
- Real-time order updates with HTMX

### 👑 Admin Flow
- Manage services (Add/Edit/Delete with image upload)
- Manage menu items per service
- Manage team members
- Assign orders to team members
- Send plans to team members (with photos)
- View all customer data and order history
- Online time reports for customers and team members
- Real-time updates with HTMX

## Technology Stack

- **Backend**: Python 3.11 + FastAPI (full async)
- **Database**: PostgreSQL + SQLAlchemy 2.0 (async) + Alembic migrations
- **Validation**: Pydantic v2 (strict mode)
- **Frontend**: Jinja2 templates + Bootstrap 5 + HTMX
- **Security**: passlib (bcrypt), HTTP-only cookies
- **File Upload**: python-multipart
- **SMS OTP**: Twilio integration
- **Logging**: Structured logging with global exception handlers

## Database Schema

```sql
User (users)
├── id, uuid, name, username, email, phone
├── hashed_password, address, role
├── is_active, created_at
└── Relationships: orders, assigned_orders, sessions

Service (services)
├── id, name, description, image_url
├── is_active, created_at
└── Relationships: menu_items, orders

MenuItem (menu_items)
├── id, service_id, name, description
├── price, image_url, is_available, created_at
└── Relationships: service, order_items

Order (orders)
├── id, order_number, customer_id, service_id
├── total_amount, address, phone, special_instructions
├── status, assigned_to, otp, otp_expiry
├── otp_attempts, created_at, updated_at
└── Relationships: customer, service, assigned_to_user, order_items

OrderItem (order_items)
├── id, order_id, menu_item_id, quantity
├── price_at_order, created_at
└── Relationships: order, menu_item

TeamMemberPlan (team_member_plans)
├── id, admin_id, team_member_id, description
├── image_url, is_read, created_at
└── Relationships: admin, team_member

UserSession (user_sessions)
├── id, user_id, login_time, logout_time
├── date, ip_address, user_agent
└── Relationships: user
