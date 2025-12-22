# File: api/team.py
from fastapi import APIRouter, Depends, HTTPException, Query, Form, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc, and_
from datetime import datetime, timedelta
from typing import List, Optional

from database import get_db
from models import User, Order, TeamMemberPlan, Service
from auth import get_current_user, require_role, is_team_member, generate_otp
from email_service import email_service
from utils import get_pagination_params, format_date

router = APIRouter()

# =================== TEAM DASHBOARD ===================

@router.get("/dashboard")
async def team_dashboard(
    user: User = Depends(is_team_member),
    db: Session = Depends(get_db)
):
    """Get team member dashboard data"""
    today = datetime.utcnow().date()
    
    # Get today's assigned orders
    assigned_orders = db.query(Order).filter(
        Order.assigned_to == user.id,
        Order.status.in_(["confirmed", "preparing", "out_for_delivery"])
    ).options(
        joinedload(Order.customer),
        joinedload(Order.service)
    ).order_by(Order.created_at.desc()).all()
    
    # Get today's completed orders
    completed_today = db.query(Order).filter(
        Order.assigned_to == user.id,
        Order.status == "delivered",
        func.date(Order.delivered_at) == today
    ).count()
    
    # Get today's plans
    today_plans = db.query(TeamMemberPlan).filter(
        (TeamMemberPlan.team_member_id == user.id) | (TeamMemberPlan.team_member_id.is_(None)),
        TeamMemberPlan.plan_date == today.isoformat()
    ).order_by(
        desc(TeamMemberPlan.priority == "high"),
        desc(TeamMemberPlan.priority == "medium"),
        TeamMemberPlan.created_at
    ).all()
    
    # Get performance stats for current month
    month_start = today.replace(day=1)
    month_orders = db.query(Order).filter(
        Order.assigned_to == user.id,
        Order.created_at >= month_start
    ).all()
    
    total_month_orders = len(month_orders)
    delivered_month_orders = sum(1 for order in month_orders if order.status == "delivered")
    month_success_rate = (delivered_month_orders / total_month_orders * 100) if total_month_orders > 0 else 0
    
    # Calculate average delivery time for month
    delivery_times = []
    for order in month_orders:
        if order.status == "delivered" and order.delivered_at and order.created_at:
            delivery_time = (order.delivered_at - order.created_at).total_seconds() / 60
            delivery_times.append(delivery_time)
    
    avg_delivery_time = sum(delivery_times) / len(delivery_times) if delivery_times else 0
    
    return {
        "member": {
            "id": user.id,
            "name": user.name,
            "phone": user.phone
        },
        "stats": {
            "assigned_orders": len(assigned_orders),
            "completed_today": completed_today,
            "month_orders": total_month_orders,
            "month_success_rate": round(month_success_rate, 2),
            "avg_delivery_time": round(avg_delivery_time, 2)
        },
        "assigned_orders": [
            {
                "id": order.id,
                "order_number": order.order_number,
                "customer": {
                    "name": order.customer.name,
                    "phone": order.customer.phone,
                    "address": f"{order.customer.address}" if order.customer.address else "N/A"
                },
                "service": {
                    "name": order.service.name,
                    "phone": order.service.phone if hasattr(order.service, 'phone') else None
                },
                "total_amount": order.total_amount,
                "status": order.status,
                "delivery_instructions": order.delivery_instructions,
                "delivery_otp": order.delivery_otp if order.status == "out_for_delivery" else None,
                "otp_expiry": order.otp_expiry if order.status == "out_for_delivery" else None,
                "estimated_delivery": format_date(order.estimated_delivery_time) if order.estimated_delivery_time else None,
                "created_at": format_date(order.created_at)
            }
            for order in assigned_orders
        ],
        "today_plans": [
            {
                "id": plan.id,
                "title": plan.title,
                "description": plan.description,
                "priority": plan.priority,
                "status": plan.status,
                "start_time": plan.start_time,
                "end_time": plan.end_time,
                "location": plan.location
            }
            for plan in today_plans
        ]
    }

@router.get("/orders")
async def get_team_orders(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    user: User = Depends(is_team_member),
    db: Session = Depends(get_db)
):
    """Get orders assigned to team member"""
    offset, limit = get_pagination_params(page, limit)
    
    # Build query
    query = db.query(Order).filter(Order.assigned_to == user.id)
    
    if status:
        query = query.filter(Order.status == status)
    
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
    
    # Get total count
    total = query.count()
    
    # Get orders with customer and service details
    orders = query.options(
        joinedload(Order.customer),
        joinedload(Order.service),
        joinedload(Order.order_items).joinedload(OrderItem.menu_item)
    ).order_by(desc(Order.created_at)).offset(offset).limit(limit).all()
    
    return {
        "orders": [
            {
                "id": order.id,
                "order_number": order.order_number,
                "customer": {
                    "name": order.customer.name,
                    "phone": order.customer.phone,
                    "address": order.customer.address
                },
                "service": {
                    "name": order.service.name,
                    "phone": order.service.phone if hasattr(order.service, 'phone') else None
                },
                "total_amount": order.total_amount,
                "status": order.status,
                "payment_status": order.payment_status,
                "delivery_instructions": order.delivery_instructions,
                "delivery_otp": order.delivery_otp if order.status == "out_for_delivery" else None,
                "estimated_delivery": order.estimated_delivery_time,
                "created_at": order.created_at,
                "delivered_at": order.delivered_at,
                "items": [
                    {
                        "name": item.menu_item.name,
                        "quantity": item.quantity,
                        "price": item.price_at_time
                    }
                    for item in order.order_items
                ]
            }
            for order in orders
        ],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit
        }
    }

@router.get("/orders/{order_id}")
async def get_team_order_details(
    order_id: int,
    user: User = Depends(is_team_member),
    db: Session = Depends(get_db)
):
    """Get order details for team member"""
    order = db.query(Order).options(
        joinedload(Order.customer),
        joinedload(Order.service),
        joinedload(Order.order_items).joinedload(OrderItem.menu_item),
        joinedload(Order.delivery_address)
    ).filter(
        Order.id == order_id,
        Order.assigned_to == user.id
    ).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or not assigned to you")
    
    return {
        "order": {
            "id": order.id,
            "order_number": order.order_number,
            "status": order.status,
            "status_history": order.status_history or [],
            "delivery_instructions": order.delivery_instructions,
            "delivery_otp": order.delivery_otp,
            "otp_expiry": order.otp_expiry,
            "estimated_delivery": order.estimated_delivery_time,
            "created_at": order.created_at
        },
        "customer": {
            "name": order.customer.name,
            "phone": order.customer.phone,
            "email": order.customer.email
        },
        "service": {
            "name": order.service.name,
            "phone": order.service.phone if hasattr(order.service, 'phone') else None,
            "address": order.service.address if hasattr(order.service, 'address') else None
        },
        "delivery_address": {
            "label": order.delivery_address.label if order.delivery_address else None,
            "address_line1": order.delivery_address.address_line1 if order.delivery_address else None,
            "address_line2": order.delivery_address.address_line2 if order.delivery_address else None,
            "city": order.delivery_address.city if order.delivery_address else None,
            "state": order.delivery_address.state if order.delivery_address else None,
            "pincode": order.delivery_address.pincode if order.delivery_address else None,
            "latitude": order.delivery_address.latitude if order.delivery_address else None,
            "longitude": order.delivery_address.longitude if order.delivery_address else None
        } if order.delivery_address else {
            "address": order.customer.address
        },
        "items": [
            {
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
            "total": order.total_amount
        }
    }

@router.post("/orders/{order_id}/update-status")
async def update_order_status_team(
    background_tasks: BackgroundTasks,
    order_id: int,
    status: str = Form(...),
    notes: Optional[str] = Form(None),
    user: User = Depends(is_team_member),
    db: Session = Depends(get_db)
):
    """Update order status (team member)"""
    # Validate status transition
    valid_statuses = ["confirmed", "preparing", "out_for_delivery", "delivered"]
    
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.assigned_to == user.id
    ).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or not assigned to you")
    
    # Validate status transition
    current_status = order.status
    
    # Define allowed transitions
    allowed_transitions = {
        "confirmed": ["preparing"],
        "preparing": ["out_for_delivery"],
        "out_for_delivery": ["delivered"],
        "delivered": []  # No further transitions
    }
    
    if status not in allowed_transitions.get(current_status, []):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot change status from {current_status} to {status}"
        )
    
    # Special handling for delivered status
    if status == "delivered":
        if not order.delivery_otp:
            raise HTTPException(status_code=400, detail="Cannot mark as delivered without OTP verification")
        
        order.delivered_at = datetime.utcnow()
        order.payment_status = "completed"
    
    # Update status
    order.status = status
    
    # Update status history
    if not order.status_history:
        order.status_history = []
    
    order.status_history.append({
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
        "changed_by": user.name,
        "notes": notes or f"Status changed from {current_status} to {status} by delivery agent"
    })
    
    db.commit()
    
    # Send status update email to customer
    if status in ["out_for_delivery", "delivered"]:
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

@router.post("/orders/{order_id}/verify-otp")
async def verify_delivery_otp(
    order_id: int,
    otp: str = Form(...),
    user: User = Depends(is_team_member),
    db: Session = Depends(get_db)
):
    """Verify delivery OTP before marking as delivered"""
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.assigned_to == user.id
    ).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or not assigned to you")
    
    if order.status != "out_for_delivery":
        raise HTTPException(
            status_code=400,
            detail="Order is not out for delivery"
        )
    
    if not order.delivery_otp:
        raise HTTPException(status_code=400, detail="No OTP required for this order")
    
    # Check OTP expiry
    if order.otp_expiry and datetime.utcnow() > order.otp_expiry:
        raise HTTPException(status_code=400, detail="OTP has expired")
    
    # Verify OTP
    if order.delivery_otp != otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    
    # Mark as delivered
    order.status = "delivered"
    order.delivered_at = datetime.utcnow()
    order.payment_status = "completed"
    
    # Update status history
    if not order.status_history:
        order.status_history = []
    
    order.status_history.append({
        "status": "delivered",
        "timestamp": datetime.utcnow().isoformat(),
        "changed_by": user.name,
        "notes": "Delivery completed with OTP verification"
    })
    
    db.commit()
    
    return {
        "success": True,
        "message": "Delivery verified and order marked as delivered"
    }

@router.get("/performance")
async def get_team_performance(
    period: str = Query("month", regex="^(week|month|year)$"),
    user: User = Depends(is_team_member),
    db: Session = Depends(get_db)
):
    """Get team member performance statistics"""
    from datetime import datetime, timedelta
    
    now = datetime.utcnow()
    
    # Define date range
    if period == "week":
        start_date = now - timedelta(days=7)
    elif period == "month":
        start_date = now - timedelta(days=30)
    else:  # year
        start_date = now - timedelta(days=365)
    
    # Get orders for period
    orders = db.query(Order).filter(
        Order.assigned_to == user.id,
        Order.created_at >= start_date
    ).order_by(desc(Order.created_at)).all()
    
    # Calculate statistics
    total_orders = len(orders)
    delivered_orders = sum(1 for order in orders if order.status == "delivered")
    cancelled_orders = sum(1 for order in orders if order.status == "cancelled")
    
    success_rate = (delivered_orders / total_orders * 100) if total_orders > 0 else 0
    
    # Calculate delivery times
    delivery_times = []
    for order in orders:
        if order.status == "delivered" and order.delivered_at and order.created_at:
            delivery_time = (order.delivered_at - order.created_at).total_seconds() / 60
            delivery_times.append(delivery_time)
    
    avg_delivery_time = sum(delivery_times) / len(delivery_times) if delivery_times else 0
    min_delivery_time = min(delivery_times) if delivery_times else 0
    max_delivery_time = max(delivery_times) if delivery_times else 0
    
    # Calculate daily performance
    daily_stats = {}
    for order in orders:
        date_str = order.created_at.date().isoformat()
        if date_str not in daily_stats:
            daily_stats[date_str] = {
                "orders": 0,
                "delivered": 0,
                "cancelled": 0
            }
        
        daily_stats[date_str]["orders"] += 1
        
        if order.status == "delivered":
            daily_stats[date_str]["delivered"] += 1
        elif order.status == "cancelled":
            daily_stats[date_str]["cancelled"] += 1
    
    # Convert to list
    daily_performance = [
        {
            "date": date,
            **stats
        }
        for date, stats in sorted(daily_stats.items(), reverse=True)
    ]
    
    # Get top services
    service_stats = {}
    for order in orders:
        service_name = order.service.name
        if service_name not in service_stats:
            service_stats[service_name] = 0
        service_stats[service_name] += 1
    
    top_services = sorted(service_stats.items(), key=lambda x: x[1], reverse=True)[:5]
    
    return {
        "period": period,
        "date_range": {
            "start": start_date,
            "end": now
        },
        "stats": {
            "total_orders": total_orders,
            "delivered_orders": delivered_orders,
            "cancelled_orders": cancelled_orders,
            "success_rate": round(success_rate, 2),
            "avg_delivery_time": round(avg_delivery_time, 2),
            "min_delivery_time": round(min_delivery_time, 2),
            "max_delivery_time": round(max_delivery_time, 2)
        },
        "daily_performance": daily_performance[:30],  # Last 30 days
        "top_services": [
            {
                "service": service,
                "orders": count
            }
            for service, count in top_services
        ],
        "recent_orders": [
            {
                "order_number": order.order_number,
                "customer": order.customer.name,
                "service": order.service.name,
                "status": order.status,
                "delivery_time": (order.delivered_at - order.created_at).total_seconds() / 60 
                                 if order.status == "delivered" and order.delivered_at else None,
                "created_at": order.created_at
            }
            for order in orders[:10]
        ]
    }

@router.get("/plans")
async def get_team_plans(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    user: User = Depends(is_team_member),
    db: Session = Depends(get_db)
):
    """Get team member plans"""
    offset, limit = get_pagination_params(page, limit)
    
    # Build query
    query = db.query(TeamMemberPlan).filter(
        (TeamMemberPlan.team_member_id == user.id) | (TeamMemberPlan.team_member_id.is_(None))
    )
    
    if status:
        query = query.filter(TeamMemberPlan.status == status)
    
    if priority:
        query = query.filter(TeamMemberPlan.priority == priority)
    
    if from_date:
        query = query.filter(TeamMemberPlan.plan_date >= from_date)
    
    if to_date:
        query = query.filter(TeamMemberPlan.plan_date <= to_date)
    
    # Get total count
    total = query.count()
    
    # Get plans
    plans = query.order_by(
        desc(TeamMemberPlan.priority == "high"),
        desc(TeamMemberPlan.priority == "medium"),
        TeamMemberPlan.plan_date.desc(),
        TeamMemberPlan.created_at.desc()
    ).offset(offset).limit(limit).all()
    
    return {
        "plans": [
            {
                "id": plan.id,
                "title": plan.title,
                "description": plan.description,
                "plan_date": plan.plan_date,
                "start_time": plan.start_time,
                "end_time": plan.end_time,
                "priority": plan.priority,
                "status": plan.status,
                "location": plan.location,
                "image_url": plan.image_url,
                "created_by": plan.admin.name if plan.admin else None,
                "created_at": plan.created_at,
                "completed_at": plan.completed_at
            }
            for plan in plans
        ],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit
        }
    }

@router.post("/plans/{plan_id}/update-status")
async def update_plan_status(
    plan_id: int,
    status: str = Form(..., regex="^(pending|in_progress|completed|cancelled)$"),
    notes: Optional[str] = Form(None),
    user: User = Depends(is_team_member),
    db: Session = Depends(get_db)
):
    """Update plan status"""
    plan = db.query(TeamMemberPlan).filter(
        TeamMemberPlan.id == plan_id,
        (TeamMemberPlan.team_member_id == user.id) | (TeamMemberPlan.team_member_id.is_(None))
    ).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found or not assigned to you")
    
    # Update status
    old_status = plan.status
    plan.status = status
    
    # Set completion time if completed
    if status == "completed":
        plan.completed_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Plan status updated from {old_status} to {status}"
    }

@router.get("/availability")
async def get_team_availability(
    user: User = Depends(is_team_member),
    db: Session = Depends(get_db)
):
    """Get team member availability and schedule"""
    # Get today's date
    today = datetime.utcnow().date()
    
    # Get plans for next 7 days
    plans = db.query(TeamMemberPlan).filter(
        (TeamMemberPlan.team_member_id == user.id) | (TeamMemberPlan.team_member_id.is_(None)),
        TeamMemberPlan.plan_date >= today.isoformat(),
        TeamMemberPlan.plan_date <= (today + timedelta(days=7)).isoformat()
    ).order_by(TeamMemberPlan.plan_date, TeamMemberPlan.start_time).all()
    
    # Get orders for next 3 days
    orders = db.query(Order).filter(
        Order.assigned_to == user.id,
        Order.status.in_(["confirmed", "preparing", "out_for_delivery"]),
        Order.created_at >= today,
        Order.created_at <= today + timedelta(days=3)
    ).order_by(Order.estimated_delivery_time).all()
    
    # Organize by date
    schedule = {}
    
    for i in range(8):  # Today + next 7 days
        date = today + timedelta(days=i)
        date_str = date.isoformat()
        
        schedule[date_str] = {
            "date": date_str,
            "day": date.strftime("%A"),
            "plans": [],
            "orders": []
        }
    
    # Add plans to schedule
    for plan in plans:
        date_str = plan.plan_date
        if date_str in schedule:
            schedule[date_str]["plans"].append({
                "id": plan.id,
                "title": plan.title,
                "start_time": plan.start_time,
                "end_time": plan.end_time,
                "priority": plan.priority,
                "status": plan.status,
                "location": plan.location
            })
    
    # Add orders to schedule
    for order in orders:
        if order.estimated_delivery_time:
            date_str = order.estimated_delivery_time.date().isoformat()
            if date_str in schedule:
                schedule[date_str]["orders"].append({
                    "id": order.id,
                    "order_number": order.order_number,
                    "customer": order.customer.name,
                    "service": order.service.name,
                    "estimated_time": order.estimated_delivery_time.strftime("%H:%M"),
                    "status": order.status
                })
    
    # Convert to list
    schedule_list = list(schedule.values())
    
    return {
        "member": {
            "name": user.name,
            "phone": user.phone,
            "is_available": True  # You can add availability status
        },
        "schedule": schedule_list,
        "today_summary": {
            "plans": len(schedule[today.isoformat()]["plans"]),
            "orders": len(schedule[today.isoformat()]["orders"]),
            "busy_hours": get_busy_hours(schedule[today.isoformat()])
        }
    }

def get_busy_hours(day_schedule):
    """Get busy hours for a day"""
    busy_hours = set()
    
    for plan in day_schedule["plans"]:
        if plan["start_time"] and plan["end_time"]:
            start_hour = int(plan["start_time"].split(":")[0])
            end_hour = int(plan["end_time"].split(":")[0])
            busy_hours.update(range(start_hour, end_hour + 1))
    
    for order in day_schedule["orders"]:
        if order["estimated_time"]:
            hour = int(order["estimated_time"].split(":")[0])
            busy_hours.add(hour)
    
    return sorted(list(busy_hours))
