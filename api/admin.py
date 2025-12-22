# File: api/admin.py
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc, and_, or_
from datetime import datetime, timedelta
from typing import List, Optional
import json
import math

from database import get_db
from models import User, Service, Order, OrderItem, MenuItem, Category, TeamMemberPlan, Review, Payment
from auth import get_current_user, require_role, is_admin, generate_otp
from utils import save_upload_file, delete_file, slugify, get_pagination_params
from email_service import email_service
from config import settings

router = APIRouter()

# =================== DASHBOARD STATISTICS ===================

@router.get("/dashboard/stats")
async def get_admin_dashboard_stats(
    period: str = Query("today", regex="^(today|week|month|year)$"),
    user: User = Depends(is_admin),
    db: Session = Depends(get_db)
):
    """Get admin dashboard statistics"""
    from datetime import datetime, timedelta
    
    now = datetime.utcnow()
    
    # Define date ranges
    if period == "today":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start_date = now - timedelta(days=7)
    elif period == "month":
        start_date = now - timedelta(days=30)
    else:  # year
        start_date = now - timedelta(days=365)
    
    # Total statistics
    total_customers = db.query(User).filter(User.role == "customer").count()
    total_team_members = db.query(User).filter(User.role == "team_member").count()
    total_services = db.query(Service).count()
    total_orders = db.query(Order).count()
    
    # Period statistics
    period_orders = db.query(Order).filter(Order.created_at >= start_date).count()
    period_revenue = db.query(func.sum(Order.total_amount)).filter(
        Order.created_at >= start_date,
        Order.status == "delivered"
    ).scalar() or 0
    
    period_customers = db.query(User).filter(
        User.created_at >= start_date,
        User.role == "customer"
    ).count()
    
    # Recent orders
    recent_orders = db.query(Order).options(
        joinedload(Order.customer),
        joinedload(Order.service)
    ).order_by(desc(Order.created_at)).limit(10).all()
    
    # Top selling services
    top_services = db.query(
        Service.name,
        func.count(Order.id).label("order_count"),
        func.sum(Order.total_amount).label("revenue")
    ).join(Order, Order.service_id == Service.id).filter(
        Order.created_at >= start_date
    ).group_by(Service.id, Service.name).order_by(desc(func.count(Order.id))).limit(5).all()
    
    # Order status distribution
    status_distribution = db.query(
        Order.status,
        func.count(Order.id).label("count")
    ).filter(Order.created_at >= start_date).group_by(Order.status).all()
    
    return {
        "period": period,
        "date_range": {
            "start": start_date,
            "end": now
        },
        "overall_stats": {
            "customers": total_customers,
            "team_members": total_team_members,
            "services": total_services,
            "orders": total_orders
        },
        "period_stats": {
            "orders": period_orders,
            "revenue": period_revenue,
            "new_customers": period_customers,
            "avg_order_value": period_revenue / period_orders if period_orders > 0 else 0
        },
        "recent_orders": [
            {
                "order_number": order.order_number,
                "customer": order.customer.name,
                "service": order.service.name,
                "amount": order.total_amount,
                "status": order.status,
                "created_at": order.created_at
            }
            for order in recent_orders
        ],
        "top_services": [
            {
                "name": name,
                "orders": order_count,
                "revenue": revenue or 0
            }
            for name, order_count, revenue in top_services
        ],
        "order_status": {status: count for status, count in status_distribution}
    }

@router.get("/dashboard/charts")
async def get_dashboard_charts(
    chart_type: str = Query("revenue", regex="^(revenue|orders|customers)$"),
    timeframe: str = Query("month", regex="^(day|week|month|year)$"),
    user: User = Depends(is_admin),
    db: Session = Depends(get_db)
):
    """Get chart data for dashboard"""
    from datetime import datetime, timedelta
    
    now = datetime.utcnow()
    
    # Define date range based on timeframe
    if timeframe == "day":
        start_date = now - timedelta(days=1)
        date_format = "%H:00"
        group_by = func.date_format(Order.created_at, "%Y-%m-%d %H:00")
    elif timeframe == "week":
        start_date = now - timedelta(days=7)
        date_format = "%a"
        group_by = func.date(Order.created_at)
    elif timeframe == "month":
        start_date = now - timedelta(days=30)
        date_format = "%d %b"
        group_by = func.date(Order.created_at)
    else:  # year
        start_date = now - timedelta(days=365)
        date_format = "%b %Y"
        group_by = func.date_format(Order.created_at, "%Y-%m")
    
    if chart_type == "revenue":
        # Revenue chart data
        data = db.query(
            group_by.label("date"),
            func.sum(Order.total_amount).label("value")
        ).filter(
            Order.created_at >= start_date,
            Order.status == "delivered"
        ).group_by(group_by).order_by(group_by).all()
    
    elif chart_type == "orders":
        # Orders chart data
        data = db.query(
            group_by.label("date"),
            func.count(Order.id).label("value")
        ).filter(
            Order.created_at >= start_date
        ).group_by(group_by).order_by(group_by).all()
    
    else:  # customers
        # Customers chart data
        data = db.query(
            group_by.label("date"),
            func.count(User.id).label("value")
        ).filter(
            User.created_at >= start_date,
            User.role == "customer"
        ).group_by(group_by).order_by(group_by).all()
    
    return {
        "chart_type": chart_type,
        "timeframe": timeframe,
        "data": [
            {
                "date": row.date,
                "value": row.value or 0
            }
            for row in data
        ]
    }

# =================== USER MANAGEMENT ===================

@router.get("/users")
async def get_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    role: Optional[str] = Query(None, regex="^(customer|team_member|admin)$"),
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    user: User = Depends(is_admin),
    db: Session = Depends(get_db)
):
    """Get users with filtering"""
    offset, limit = get_pagination_params(page, limit)
    
    # Build query
    query = db.query(User)
    
    if role:
        query = query.filter(User.role == role)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                User.name.ilike(search_term),
                User.email.ilike(search_term),
                User.phone.ilike(search_term),
                User.username.ilike(search_term)
            )
        )
    
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    
    # Get total count
    total = query.count()
    
    # Get users
    users = query.order_by(desc(User.created_at)).offset(offset).limit(limit).all()
    
    # Get order counts for each user
    user_stats = {}
    for usr in users:
        order_count = db.query(Order).filter(Order.customer_id == usr.id).count()
        user_stats[usr.id] = {
            "order_count": order_count,
            "total_spent": db.query(func.sum(Order.total_amount)).filter(
                Order.customer_id == usr.id,
                Order.status == "delivered"
            ).scalar() or 0
        }
    
    return {
        "users": [
            {
                "id": usr.id,
                "name": usr.name,
                "email": usr.email,
                "phone": usr.phone,
                "role": usr.role,
                "is_active": usr.is_active,
                "is_verified": usr.is_verified,
                "created_at": usr.created_at,
                "last_login": usr.last_login,
                "order_count": user_stats[usr.id]["order_count"],
                "total_spent": user_stats[usr.id]["total_spent"]
            }
            for usr in users
        ],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": math.ceil(total / limit) if limit > 0 else 0
        }
    }

@router.post("/users/{user_id}/update-role")
async def update_user_role(
    user_id: int,
    role: str = Form(..., regex="^(customer|team_member|admin)$"),
    user: User = Depends(is_admin),
    db: Session = Depends(get_db)
):
    """Update user role"""
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent changing own role
    if target_user.id == user.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")
    
    target_user.role = role
    db.commit()
    
    return {
        "success": True,
        "message": f"User role updated to {role}"
    }

@router.post("/users/{user_id}/toggle-active")
async def toggle_user_active(
    user_id: int,
    user: User = Depends(is_admin),
    db: Session = Depends(get_db)
):
    """Toggle user active status"""
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent deactivating yourself
    if target_user.id == user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    
    target_user.is_active = not target_user.is_active
    db.commit()
    
    status = "activated" if target_user.is_active else "deactivated"
    
    return {
        "success": True,
        "message": f"User {status} successfully"
    }

@router.get("/users/{user_id}/details")
async def get_user_details(
    user_id: int,
    user: User = Depends(is_admin),
    db: Session = Depends(get_db)
):
    """Get detailed user information"""
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get user orders
    orders = db.query(Order).filter(Order.customer_id == user_id).order_by(
        desc(Order.created_at)
    ).limit(20).all()
    
    # Get user addresses
    from models import UserAddress
    addresses = db.query(UserAddress).filter(
        UserAddress.user_id == user_id
    ).all()
    
    # Calculate statistics
    total_orders = len(orders)
    completed_orders = sum(1 for order in orders if order.status == "delivered")
    total_spent = sum(order.total_amount for order in orders if order.status == "delivered")
    
    # Get favorite service
    favorite_service = db.query(
        Service.name,
        func.count(Order.id).label("count")
    ).join(Order, Order.service_id == Service.id).filter(
        Order.customer_id == user_id
    ).group_by(Service.id, Service.name).order_by(func.count(Order.id).desc()).first()
    
    return {
        "user": {
            "id": target_user.id,
            "name": target_user.name,
            "email": target_user.email,
            "phone": target_user.phone,
            "role": target_user.role,
            "is_active": target_user.is_active,
            "is_verified": target_user.is_verified,
            "created_at": target_user.created_at,
            "last_login": target_user.last_login,
            "address": target_user.address
        },
        "stats": {
            "total_orders": total_orders,
            "completed_orders": completed_orders,
            "cancelled_orders": total_orders - completed_orders,
            "total_spent": total_spent,
            "avg_order_value": total_spent / completed_orders if completed_orders > 0 else 0,
            "favorite_service": favorite_service[0] if favorite_service else None,
            "favorite_service_orders": favorite_service[1] if favorite_service else 0
        },
        "addresses": [
            {
                "id": addr.id,
                "label": addr.label,
                "address": f"{addr.address_line1}, {addr.city}, {addr.state} - {addr.pincode}",
                "is_default": addr.is_default
            }
            for addr in addresses
        ],
        "recent_orders": [
            {
                "order_number": order.order_number,
                "service": order.service.name if order.service else None,
                "amount": order.total_amount,
                "status": order.status,
                "created_at": order.created_at
            }
            for order in orders[:10]
        ]
    }

# =================== ORDER MANAGEMENT ===================

@router.get("/orders")
async def get_all_orders(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    service_id: Optional[int] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    user: User = Depends(is_admin),
    db: Session = Depends(get_db)
):
    """Get all orders with filtering"""
    offset, limit = get_pagination_params(page, limit)
    
    # Build query
    query = db.query(Order).options(
        joinedload(Order.customer),
        joinedload(Order.service),
        joinedload(Order.team_member)
    )
    
    if status:
        query = query.filter(Order.status == status)
    
    if service_id:
        query = query.filter(Order.service_id == service_id)
    
    if from_date:
        try:
            from_dt = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
            query = query.filter(Order.created_at >= from_dt)
        except ValueError:
            pass
    
    if to_date:
        try:
            to_dt = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
            query = query.filter(Order.created_at <= to_dt)
        except ValueError:
            pass
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Order.order_number.ilike(search_term),
                User.name.ilike(search_term),
                User.phone.ilike(search_term)
            )
        ).join(User, Order.customer_id == User.id)
    
    # Get total count
    total = query.count()
    
    # Get orders
    orders = query.order_by(desc(Order.created_at)).offset(offset).limit(limit).all()
    
    return {
        "orders": [
            {
                "id": order.id,
                "order_number": order.order_number,
                "customer": {
                    "id": order.customer.id,
                    "name": order.customer.name,
                    "phone": order.customer.phone
                },
                "service": {
                    "id": order.service.id,
                    "name": order.service.name
                },
                "team_member": {
                    "id": order.team_member.id,
                    "name": order.team_member.name
                } if order.team_member else None,
                "total_amount": order.total_amount,
                "status": order.status,
                "payment_status": order.payment_status,
                "created_at": order.created_at,
                "estimated_delivery": order.estimated_delivery_time
            }
            for order in orders
        ],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": math.ceil(total / limit) if limit > 0 else 0
        }
    }

@router.get("/orders/{order_id}")
async def get_order_admin(
    order_id: int,
    user: User = Depends(is_admin),
    db: Session = Depends(get_db)
):
    """Get order details (admin view)"""
    order = db.query(Order).options(
        joinedload(Order.customer),
        joinedload(Order.service),
        joinedload(Order.team_member),
        joinedload(Order.order_items).joinedload(OrderItem.menu_item),
        joinedload(Order.delivery_address)
    ).filter(Order.id == order_id).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return {
        "order": {
            "id": order.id,
            "order_number": order.order_number,
            "status": order.status,
            "status_history": order.status_history or [],
            "payment_method": order.payment_method,
            "payment_status": order.payment_status,
            "created_at": order.created_at,
            "updated_at": order.updated_at,
            "delivered_at": order.delivered_at,
            "estimated_delivery": order.estimated_delivery_time,
            "delivery_instructions": order.delivery_instructions,
            "delivery_otp": order.delivery_otp,
            "otp_expiry": order.otp_expiry
        },
        "customer": {
            "id": order.customer.id,
            "name": order.customer.name,
            "email": order.customer.email,
            "phone": order.customer.phone,
            "address": order.customer.address
        },
        "service": {
            "id": order.service.id,
            "name": order.service.name,
            "phone": order.service.phone if hasattr(order.service, 'phone') else None
        },
        "delivery_address": {
            "label": order.delivery_address.label if order.delivery_address else None,
            "address_line1": order.delivery_address.address_line1 if order.delivery_address else None,
            "address_line2": order.delivery_address.address_line2 if order.delivery_address else None,
            "city": order.delivery_address.city if order.delivery_address else None,
            "state": order.delivery_address.state if order.delivery_address else None,
            "pincode": order.delivery_address.pincode if order.delivery_address else None
        },
        "team_member": {
            "id": order.team_member.id if order.team_member else None,
            "name": order.team_member.name if order.team_member else None,
            "phone": order.team_member.phone if order.team_member else None
        },
        "items": [
            {
                "id": item.menu_item.id,
                "name": item.menu_item.name,
                "quantity": item.quantity,
                "price": item.price_at_time,
                "total": item.price_at_time * item.quantity,
                "special_instructions": item.special_instructions
            }
            for item in order.order_items
        ],
        "totals": {
            "subtotal": order.subtotal,
            "tax": order.tax_amount,
            "delivery_charge": order.delivery_charge,
            "discount": order.discount_amount,
            "total": order.total_amount
        }
    }

@router.post("/orders/{order_id}/update-status")
async def update_order_status_admin(
    background_tasks: BackgroundTasks,
    order_id: int,
    status: str = Form(...),
    notes: Optional[str] = Form(None),
    assign_to: Optional[int] = Form(None),
    user: User = Depends(is_admin),
    db: Session = Depends(get_db)
):
    """Update order status (admin)"""
    valid_statuses = ["pending", "confirmed", "preparing", "out_for_delivery", "delivered", "cancelled"]
    
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Handle assignment
    if assign_to:
        team_member = db.query(User).filter(
            User.id == assign_to,
            User.role == "team_member",
            User.is_active == True
        ).first()
        
        if not team_member:
            raise HTTPException(status_code=404, detail="Team member not found")
        
        order.assigned_to = assign_to
        
        # Send assignment email
        order_details = {
            "order_number": order.order_number,
            "customer_name": order.customer.name,
            "delivery_address": f"{order.delivery_address.address_line1}, {order.delivery_address.city}" if order.delivery_address else order.customer.address,
            "estimated_delivery": order.estimated_delivery_time.strftime("%I:%M %p") if order.estimated_delivery_time else None,
            "delivery_otp": order.delivery_otp
        }
        
        background_tasks.add_task(
            email_service.send_team_assignment_email,
            team_member.email,
            team_member.name,
            order_details
        )
    
    # Update status
    old_status = order.status
    order.status = status
    
    # Handle delivered status
    if status == "delivered":
        order.delivered_at = datetime.utcnow()
        order.payment_status = "completed"
    
    # Handle cancelled status
    if status == "cancelled":
        order.payment_status = "refunded" if order.payment_status == "completed" else "cancelled"
    
    # Update status history
    if not order.status_history:
        order.status_history = []
    
    order.status_history.append({
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
        "changed_by": user.name,
        "notes": notes or f"Status changed from {old_status} to {status}"
    })
    
    db.commit()
    
    # Send status update email to customer
    if status in ["preparing", "out_for_delivery", "delivered", "cancelled"]:
        order_details = {
            "order_number": order.order_number,
            "customer_name": order.customer.name,
            "status": status,
            "delivery_otp": order.delivery_otp if status == "out_for_delivery" else None
        }
        
        background_tasks.add_task(
            email_service.send_order_status_update,
            order.customer.email,
            order_details
        )
    
    return {
        "success": True,
        "message": f"Order status updated to {status}"
    }

@router.post("/orders/{order_id}/assign")
async def assign_order(
    background_tasks: BackgroundTasks,
    order_id: int,
    team_member_id: int = Form(...),
    user: User = Depends(is_admin),
    db: Session = Depends(get_db)
):
    """Assign order to team member"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    team_member = db.query(User).filter(
        User.id == team_member_id,
        User.role == "team_member",
        User.is_active == True
    ).first()
    
    if not team_member:
        raise HTTPException(status_code=404, detail="Team member not found")
    
    # Update order
    order.assigned_to = team_member_id
    order.status = "confirmed" if order.status == "pending" else order.status
    
    # Add to status history
    if not order.status_history:
        order.status_history = []
    
    order.status_history.append({
        "status": order.status,
        "timestamp": datetime.utcnow().isoformat(),
        "changed_by": user.name,
        "notes": f"Assigned to {team_member.name}"
    })
    
    db.commit()
    
    # Send assignment email
    order_details = {
        "order_number": order.order_number,
        "customer_name": order.customer.name,
        "delivery_address": f"{order.delivery_address.address_line1}, {order.delivery_address.city}" if order.delivery_address else order.customer.address,
        "estimated_delivery": order.estimated_delivery_time.strftime("%I:%M %p") if order.estimated_delivery_time else None,
        "delivery_otp": order.delivery_otp
    }
    
    background_tasks.add_task(
        email_service.send_team_assignment_email,
        team_member.email,
        team_member.name,
        order_details
    )
    
    return {
        "success": True,
        "message": f"Order assigned to {team_member.name}"
    }

@router.post("/orders/{order_id}/regenerate-otp")
async def regenerate_delivery_otp(
    order_id: int,
    user: User = Depends(is_admin),
    db: Session = Depends(get_db)
):
    """Regenerate delivery OTP"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.status != "out_for_delivery":
        raise HTTPException(
            status_code=400,
            detail="Order is not out for delivery"
        )
    
    # Generate new OTP
    new_otp = generate_otp()
    otp_expiry = datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)
    
    order.delivery_otp = new_otp
    order.otp_expiry = otp_expiry
    
    db.commit()
    
    return {
        "success": True,
        "message": "OTP regenerated successfully",
        "otp": new_otp,
        "expiry": otp_expiry
    }

# =================== SERVICE MANAGEMENT ===================

@router.get("/services/stats")
async def get_services_stats(
    user: User = Depends(is_admin),
    db: Session = Depends(get_db)
):
    """Get services statistics"""
    services = db.query(Service).all()
    
    service_stats = []
    for service in services:
        # Order statistics for this service
        total_orders = db.query(Order).filter(Order.service_id == service.id).count()
        completed_orders = db.query(Order).filter(
            Order.service_id == service.id,
            Order.status == "delivered"
        ).count()
        
        total_revenue = db.query(func.sum(Order.total_amount)).filter(
            Order.service_id == service.id,
            Order.status == "delivered"
        ).scalar() or 0
        
        avg_rating = service.rating
        total_reviews = service.total_reviews
        
        service_stats.append({
            "id": service.id,
            "name": service.name,
            "is_active": service.is_active,
            "is_featured": service.is_featured,
            "total_orders": total_orders,
            "completed_orders": completed_orders,
            "cancelled_orders": total_orders - completed_orders,
            "total_revenue": total_revenue,
            "avg_order_value": total_revenue / completed_orders if completed_orders > 0 else 0,
            "rating": avg_rating,
            "total_reviews": total_reviews
        })
    
    # Sort by revenue
    service_stats.sort(key=lambda x: x["total_revenue"], reverse=True)
    
    return {
        "services": service_stats,
        "summary": {
            "total_services": len(services),
            "active_services": sum(1 for s in services if s.is_active),
            "featured_services": sum(1 for s in services if s.is_featured),
            "total_revenue": sum(s["total_revenue"] for s in service_stats)
        }
    }

# =================== TEAM MANAGEMENT ===================

@router.get("/team/stats")
async def get_team_stats(
    user: User = Depends(is_admin),
    db: Session = Depends(get_db)
):
    """Get team member statistics"""
    team_members = db.query(User).filter(
        User.role == "team_member",
        User.is_active == True
    ).all()
    
    team_stats = []
    for member in team_members:
        # Get assigned orders
        assigned_orders = db.query(Order).filter(
            Order.assigned_to == member.id
        ).all()
        
        # Get delivered orders (today)
        today = datetime.utcnow().date()
        delivered_today = db.query(Order).filter(
            Order.assigned_to == member.id,
            Order.status == "delivered",
            func.date(Order.delivered_at) == today
        ).count()
        
        # Calculate performance metrics
        total_assigned = len(assigned_orders)
        total_delivered = sum(1 for order in assigned_orders if order.status == "delivered")
        total_cancelled = sum(1 for order in assigned_orders if order.status == "cancelled")
        
        success_rate = (total_delivered / total_assigned * 100) if total_assigned > 0 else 0
        
        # Average delivery time
        delivery_times = []
        for order in assigned_orders:
            if order.status == "delivered" and order.delivered_at and order.created_at:
                delivery_time = (order.delivered_at - order.created_at).total_seconds() / 60  # minutes
                delivery_times.append(delivery_time)
        
        avg_delivery_time = sum(delivery_times) / len(delivery_times) if delivery_times else 0
        
        team_stats.append({
            "id": member.id,
            "name": member.name,
            "phone": member.phone,
            "email": member.email,
            "total_assigned": total_assigned,
            "total_delivered": total_delivered,
            "total_cancelled": total_cancelled,
            "delivered_today": delivered_today,
            "success_rate": round(success_rate, 2),
            "avg_delivery_time": round(avg_delivery_time, 2),
            "last_active": member.last_login
        })
    
    # Sort by delivered orders
    team_stats.sort(key=lambda x: x["total_delivered"], reverse=True)
    
    return {
        "team_members": team_stats,
        "summary": {
            "total_members": len(team_members),
            "total_delivered": sum(m["total_delivered"] for m in team_stats),
            "avg_success_rate": sum(m["success_rate"] for m in team_stats) / len(team_stats) if team_stats else 0,
            "active_today": sum(1 for m in team_stats if m["delivered_today"] > 0)
        }
    }

@router.get("/team/{member_id}/performance")
async def get_team_member_performance(
    member_id: int,
    period: str = Query("month", regex="^(week|month|year)$"),
    user: User = Depends(is_admin),
    db: Session = Depends(get_db)
):
    """Get team member performance details"""
    member = db.query(User).filter(
        User.id == member_id,
        User.role == "team_member"
    ).first()
    
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    
    # Calculate date range
    now = datetime.utcnow()
    
    if period == "week":
        start_date = now - timedelta(days=7)
    elif period == "month":
        start_date = now - timedelta(days=30)
    else:  # year
        start_date = now - timedelta(days=365)
    
    # Get orders for period
    orders = db.query(Order).filter(
        Order.assigned_to == member_id,
        Order.created_at >= start_date
    ).order_by(desc(Order.created_at)).all()
    
    # Calculate daily performance
    daily_stats = {}
    for order in orders:
        date_str = order.created_at.date().isoformat()
        if date_str not in daily_stats:
            daily_stats[date_str] = {
                "orders": 0,
                "delivered": 0,
                "cancelled": 0,
                "revenue": 0
            }
        
        daily_stats[date_str]["orders"] += 1
        
        if order.status == "delivered":
            daily_stats[date_str]["delivered"] += 1
            daily_stats[date_str]["revenue"] += order.total_amount
        elif order.status == "cancelled":
            daily_stats[date_str]["cancelled"] += 1
    
    # Convert to list sorted by date
    daily_performance = [
        {
            "date": date,
            **stats
        }
        for date, stats in sorted(daily_stats.items(), reverse=True)
    ]
    
    # Calculate overall performance
    total_orders = len(orders)
    delivered_orders = sum(1 for order in orders if order.status == "delivered")
    cancelled_orders = sum(1 for order in orders if order.status == "cancelled")
    
    success_rate = (delivered_orders / total_orders * 100) if total_orders > 0 else 0
    
    # Calculate average delivery time
    delivery_times = []
    for order in orders:
        if order.status == "delivered" and order.delivered_at and order.created_at:
            delivery_time = (order.delivered_at - order.created_at).total_seconds() / 60
            delivery_times.append(delivery_time)
    
    avg_delivery_time = sum(delivery_times) / len(delivery_times) if delivery_times else 0
    
    return {
        "member": {
            "id": member.id,
            "name": member.name,
            "phone": member.phone,
            "email": member.email,
            "joined_date": member.created_at
        },
        "performance": {
            "period": period,
            "total_orders": total_orders,
            "delivered_orders": delivered_orders,
            "cancelled_orders": cancelled_orders,
            "success_rate": round(success_rate, 2),
            "avg_delivery_time": round(avg_delivery_time, 2),
            "total_revenue": sum(order.total_amount for order in orders if order.status == "delivered")
        },
        "daily_performance": daily_performance[:30],  # Last 30 days
        "recent_orders": [
            {
                "order_number": order.order_number,
                "customer": order.customer.name,
                "service": order.service.name,
                "status": order.status,
                "amount": order.total_amount,
                "created_at": order.created_at,
                "delivered_at": order.delivered_at
            }
            for order in orders[:20]
        ]
    }

# =================== PAYMENT MANAGEMENT ===================

@router.get("/payments")
async def get_payments(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    payment_method: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    user: User = Depends(is_admin),
    db: Session = Depends(get_db)
):
    """Get payment records"""
    offset, limit = get_pagination_params(page, limit)
    
    # Build query
    query = db.query(Payment).options(
        joinedload(Payment.order).joinedload(Order.customer),
        joinedload(Payment.user)
    )
    
    if status:
        query = query.filter(Payment.status == status)
    
    if payment_method:
        query = query.filter(Payment.payment_method == payment_method)
    
    if from_date:
        try:
            from_dt = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
            query = query.filter(Payment.created_at >= from_dt)
        except ValueError:
            pass
    
    if to_date:
        try:
            to_dt = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
            query = query.filter(Payment.created_at <= to_dt)
        except ValueError:
            pass
    
    # Get total count
    total = query.count()
    
    # Get payments
    payments = query.order_by(desc(Payment.created_at)).offset(offset).limit(limit).all()
    
    return {
        "payments": [
            {
                "id": payment.id,
                "order_number": payment.order.order_number if payment.order else None,
                "customer": payment.user.name if payment.user else None,
                "amount": payment.amount,
                "payment_method": payment.payment_method,
                "payment_gateway": payment.payment_gateway,
                "status": payment.status,
                "gateway_transaction_id": payment.gateway_transaction_id,
                "created_at": payment.created_at,
                "updated_at": payment.updated_at
            }
            for payment in payments
        ],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": math.ceil(total / limit) if limit > 0 else 0
        }
    }

@router.get("/payments/stats")
async def get_payment_stats(
    period: str = Query("month", regex="^(day|week|month|year)$"),
    user: User = Depends(is_admin),
    db: Session = Depends(get_db)
):
    """Get payment statistics"""
    from datetime import datetime, timedelta
    
    now = datetime.utcnow()
    
    # Define date range
    if period == "day":
        start_date = now - timedelta(days=1)
    elif period == "week":
        start_date = now - timedelta(days=7)
    elif period == "month":
        start_date = now - timedelta(days=30)
    else:  # year
        start_date = now - timedelta(days=365)
    
    # Total payments
    total_payments = db.query(Payment).filter(Payment.created_at >= start_date).count()
    total_amount = db.query(func.sum(Payment.amount)).filter(
        Payment.created_at >= start_date,
        Payment.status == "completed"
    ).scalar() or 0
    
    # Payments by method
    method_stats = db.query(
        Payment.payment_method,
        func.count(Payment.id).label("count"),
        func.sum(Payment.amount).label("amount")
    ).filter(
        Payment.created_at >= start_date,
        Payment.status == "completed"
    ).group_by(Payment.payment_method).all()
    
    # Payments by status
    status_stats = db.query(
        Payment.status,
        func.count(Payment.id).label("count"),
        func.sum(Payment.amount).label("amount")
    ).filter(Payment.created_at >= start_date).group_by(Payment.status).all()
    
    # Failed payments
    failed_payments = db.query(Payment).filter(
        Payment.created_at >= start_date,
        Payment.status == "failed"
    ).count()
    
    # Pending payments
    pending_payments = db.query(Payment).filter(
        Payment.created_at >= start_date,
        Payment.status == "pending"
    ).count()
    
    return {
        "period": period,
        "summary": {
            "total_payments": total_payments,
            "total_amount": total_amount,
            "failed_payments": failed_payments,
            "pending_payments": pending_payments,
            "avg_payment_value": total_amount / total_payments if total_payments > 0 else 0
        },
        "by_method": [
            {
                "method": method,
                "count": count,
                "amount": amount or 0
            }
            for method, count, amount in method_stats
        ],
        "by_status": [
            {
                "status": status,
                "count": count,
                "amount": amount or 0
            }
            for status, count, amount in status_stats
        ]
    }
