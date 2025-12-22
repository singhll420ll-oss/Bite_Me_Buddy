# File: api/orders.py
from fastapi import APIRouter, Depends, HTTPException, Form, Query, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import List, Optional
import json

from database import get_db
from models import Order, OrderItem, MenuItem, Service, User, UserAddress, Payment
from auth import get_current_user, require_role, generate_otp
from utils import generate_order_number, calculate_tax_amount, get_estimated_delivery_time
from email_service import email_service
from config import settings

router = APIRouter()

# =================== ORDER CREATION ===================

@router.post("/")
async def create_order(
    background_tasks: BackgroundTasks,
    service_id: int = Form(...),
    address_id: Optional[int] = Form(None),
    delivery_instructions: Optional[str] = Form(None),
    payment_method: str = Form("cash"),
    items: str = Form(...),  # JSON string: [{"id": 1, "quantity": 2, "instructions": ""}]
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new order"""
    # Parse items
    try:
        cart_items = json.loads(items)
        if not cart_items:
            raise HTTPException(status_code=400, detail="Cart is empty")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid cart data")
    
    # Get service
    service = db.query(Service).filter(
        Service.id == service_id,
        Service.is_active == True
    ).first()
    
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    # Check if service is open
    if not is_service_open(service):
        raise HTTPException(status_code=400, detail="Service is currently closed")
    
    # Get delivery address
    if address_id:
        address = db.query(UserAddress).filter(
            UserAddress.id == address_id,
            UserAddress.user_id == user.id
        ).first()
        
        if not address:
            raise HTTPException(status_code=404, detail="Address not found")
        
        delivery_address = f"{address.address_line1}"
        if address.address_line2:
            delivery_address += f", {address.address_line2}"
        delivery_address += f", {address.city}, {address.state} - {address.pincode}"
    else:
        # Use user's default address
        address = db.query(UserAddress).filter(
            UserAddress.user_id == user.id,
            UserAddress.is_default == True
        ).first()
        
        if not address:
            raise HTTPException(status_code=400, detail="Please add a delivery address")
        
        delivery_address = f"{address.address_line1}"
        if address.address_line2:
            delivery_address += f", {address.address_line2}"
        delivery_address += f", {address.city}, {address.state} - {address.pincode}"
    
    # Calculate order totals
    subtotal = 0
    order_items_data = []
    unavailable_items = []
    
    for item in cart_items:
        menu_item_id = item.get("id")
        quantity = item.get("quantity", 1)
        special_instructions = item.get("instructions", "")
        
        if quantity < 1:
            continue
        
        menu_item = db.query(MenuItem).filter(
            MenuItem.id == menu_item_id,
            MenuItem.is_available == True,
            MenuItem.service_id == service_id
        ).first()
        
        if not menu_item:
            unavailable_items.append(str(menu_item_id))
            continue
        
        item_total = menu_item.price * quantity
        if menu_item.discounted_price:
            item_total = menu_item.discounted_price * quantity
        
        subtotal += item_total
        
        order_items_data.append({
            "menu_item": menu_item,
            "quantity": quantity,
            "price": menu_item.discounted_price or menu_item.price,
            "instructions": special_instructions
        })
    
    if unavailable_items:
        raise HTTPException(
            status_code=400,
            detail=f"Some items are unavailable: {', '.join(unavailable_items)}"
        )
    
    if subtotal < service.min_order_amount:
        raise HTTPException(
            status_code=400,
            detail=f"Minimum order amount is ₹{service.min_order_amount}"
        )
    
    # Calculate charges
    tax_amount = calculate_tax_amount(subtotal, settings.TAX_RATE)
    delivery_charge = service.delivery_fee if subtotal < settings.FREE_DELIVERY_THRESHOLD else 0
    total_amount = subtotal + tax_amount + delivery_charge
    
    # Generate OTP for delivery verification
    delivery_otp = generate_otp()
    otp_expiry = datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)
    
    # Create order
    order = Order(
        order_number=generate_order_number(),
        customer_id=user.id,
        service_id=service_id,
        delivery_address_id=address.id if address else None,
        subtotal=subtotal,
        tax_amount=tax_amount,
        delivery_charge=delivery_charge,
        total_amount=total_amount,
        delivery_instructions=delivery_instructions,
        estimated_delivery_time=get_estimated_delivery_time(
            service.preparation_time,
            distance_km=5  # You can implement distance calculation
        ),
        delivery_otp=delivery_otp,
        otp_expiry=otp_expiry,
        payment_method=payment_method,
        status="pending",
        status_history=[{
            "status": "pending",
            "timestamp": datetime.utcnow().isoformat(),
            "note": "Order created"
        }]
    )
    
    db.add(order)
    db.flush()  # Get order ID
    
    # Create order items
    for item_data in order_items_data:
        order_item = OrderItem(
            order_id=order.id,
            menu_item_id=item_data["menu_item"].id,
            quantity=item_data["quantity"],
            price_at_time=item_data["price"],
            special_instructions=item_data["instructions"]
        )
        db.add(order_item)
    
    # Create initial payment record
    payment = Payment(
        order_id=order.id,
        user_id=user.id,
        payment_method=payment_method,
        amount=total_amount,
        status="pending"
    )
    db.add(payment)
    
    db.commit()
    db.refresh(order)
    
    # Send confirmation email in background
    order_details = {
        "order_number": order.order_number,
        "customer_name": user.name,
        "total_amount": total_amount,
        "delivery_address": delivery_address,
        "estimated_delivery": order.estimated_delivery_time.strftime("%I:%M %p"),
        "items": [
            {
                "name": item_data["menu_item"].name,
                "quantity": item_data["quantity"],
                "price": item_data["price"]
            }
            for item_data in order_items_data
        ]
    }
    
    background_tasks.add_task(
        email_service.send_order_confirmation,
        user.email,
        order_details
    )
    
    # If payment method is online, initiate payment
    if payment_method in ["card", "upi"]:
        payment_url = await initiate_online_payment(order, payment)
        
        return {
            "success": True,
            "message": "Order created. Please complete payment.",
            "order": {
                "id": order.id,
                "order_number": order.order_number,
                "total": total_amount,
                "status": order.status,
                "payment_status": "pending"
            },
            "payment_url": payment_url
        }
    
    return {
        "success": True,
        "message": "Order created successfully",
        "order": {
            "id": order.id,
            "order_number": order.order_number,
            "total": total_amount,
            "status": order.status,
            "payment_status": "pending",
            "delivery_otp": delivery_otp
        }
    }

@router.post("/calculate")
async def calculate_order(
    service_id: int = Form(...),
    items: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Calculate order total without creating order"""
    try:
        cart_items = json.loads(items)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid cart data")
    
    # Get service
    service = db.query(Service).filter(
        Service.id == service_id,
        Service.is_active == True
    ).first()
    
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    # Calculate subtotal
    subtotal = 0
    item_details = []
    
    for item in cart_items:
        menu_item_id = item.get("id")
        quantity = item.get("quantity", 1)
        
        if quantity < 1:
            continue
        
        menu_item = db.query(MenuItem).filter(
            MenuItem.id == menu_item_id,
            MenuItem.is_available == True,
            MenuItem.service_id == service_id
        ).first()
        
        if not menu_item:
            continue
        
        item_price = menu_item.discounted_price or menu_item.price
        item_total = item_price * quantity
        
        subtotal += item_total
        
        item_details.append({
            "id": menu_item.id,
            "name": menu_item.name,
            "quantity": quantity,
            "unit_price": item_price,
            "total": item_total,
            "image_url": menu_item.image_url
        })
    
    # Calculate charges
    tax_amount = calculate_tax_amount(subtotal, settings.TAX_RATE)
    delivery_charge = service.delivery_fee if subtotal < settings.FREE_DELIVERY_THRESHOLD else 0
    total_amount = subtotal + tax_amount + delivery_charge
    
    return {
        "breakdown": {
            "subtotal": subtotal,
            "tax": tax_amount,
            "delivery_charge": delivery_charge,
            "total": total_amount
        },
        "items": item_details,
        "service": {
            "name": service.name,
            "delivery_fee": service.delivery_fee,
            "free_delivery_threshold": settings.FREE_DELIVERY_THRESHOLD,
            "min_order_amount": service.min_order_amount
        }
    }

# =================== ORDER MANAGEMENT ===================

@router.get("/")
async def get_orders(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    status: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's orders with pagination"""
    from utils import get_pagination_params
    
    offset, limit = get_pagination_params(page, limit)
    
    # Build query
    query = db.query(Order).filter(Order.customer_id == user.id)
    
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
    
    # Get orders with related data
    orders = query.options(
        joinedload(Order.service),
        joinedload(Order.order_items).joinedload(OrderItem.menu_item)
    ).order_by(Order.created_at.desc()).offset(offset).limit(limit).all()
    
    return {
        "orders": [
            {
                "id": order.id,
                "order_number": order.order_number,
                "service": {
                    "id": order.service.id,
                    "name": order.service.name,
                    "image_url": order.service.image_url
                },
                "total_amount": order.total_amount,
                "status": order.status,
                "payment_status": order.payment_status,
                "created_at": order.created_at,
                "delivered_at": order.delivered_at,
                "estimated_delivery": order.estimated_delivery_time,
                "items": [
                    {
                        "name": item.menu_item.name,
                        "quantity": item.quantity,
                        "price": item.price_at_time,
                        "total": item.price_at_time * item.quantity
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

@router.get("/{order_id}")
async def get_order_details(
    order_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get order details"""
    order = db.query(Order).options(
        joinedload(Order.service),
        joinedload(Order.order_items).joinedload(OrderItem.menu_item),
        joinedload(Order.team_member),
        joinedload(Order.delivery_address)
    ).filter(
        Order.id == order_id,
        Order.customer_id == user.id
    ).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Calculate item totals
    items_total = sum(item.price_at_time * item.quantity for item in order.order_items)
    
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
            "delivery_otp": order.delivery_otp if order.status == "out_for_delivery" else None,
            "otp_expiry": order.otp_expiry if order.status == "out_for_delivery" else None
        },
        "service": {
            "id": order.service.id,
            "name": order.service.name,
            "image_url": order.service.image_url,
            "phone": order.service.phone if hasattr(order.service, 'phone') else None
        },
        "delivery_address": {
            "address_line1": order.delivery_address.address_line1 if order.delivery_address else None,
            "address_line2": order.delivery_address.address_line2 if order.delivery_address else None,
            "city": order.delivery_address.city if order.delivery_address else None,
            "state": order.delivery_address.state if order.delivery_address else None,
            "pincode": order.delivery_address.pincode if order.delivery_address else None
        } if order.delivery_address else None,
        "team_member": {
            "name": order.team_member.name if order.team_member else None,
            "phone": order.team_member.phone if order.team_member else None
        } if order.team_member else None,
        "items": [
            {
                "id": item.menu_item.id,
                "name": item.menu_item.name,
                "quantity": item.quantity,
                "price": item.price_at_time,
                "total": item.price_at_time * item.quantity,
                "special_instructions": item.special_instructions,
                "image_url": item.menu_item.image_url
            }
            for item in order.order_items
        ],
        "totals": {
            "items": items_total,
            "tax": order.tax_amount,
            "delivery_charge": order.delivery_charge,
            "discount": order.discount_amount,
            "total": order.total_amount
        }
    }

@router.post("/{order_id}/cancel")
async def cancel_order(
    order_id: int,
    reason: Optional[str] = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel an order"""
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.customer_id == user.id
    ).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Check if order can be cancelled
    if order.status not in ["pending", "confirmed"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel order with status: {order.status}"
        )
    
    # Check if order was placed more than 10 minutes ago
    time_since_order = datetime.utcnow() - order.created_at
    if time_since_order.total_seconds() > 600:  # 10 minutes
        raise HTTPException(
            status_code=400,
            detail="Order can only be cancelled within 10 minutes of placement"
        )
    
    # Update order status
    order.status = "cancelled"
    order.payment_status = "refunded" if order.payment_status == "completed" else "cancelled"
    
    # Add to status history
    if not order.status_history:
        order.status_history = []
    
    order.status_history.append({
        "status": "cancelled",
        "timestamp": datetime.utcnow().isoformat(),
        "note": f"Cancelled by customer. Reason: {reason or 'Not specified'}"
    })
    
    db.commit()
    
    return {
        "success": True,
        "message": "Order cancelled successfully"
    }

@router.post("/{order_id}/verify-delivery")
async def verify_delivery(
    order_id: int,
    otp: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Verify delivery with OTP"""
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.customer_id == user.id
    ).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.status != "out_for_delivery":
        raise HTTPException(
            status_code=400,
            detail="Order is not out for delivery"
        )
    
    if not order.delivery_otp:
        raise HTTPException(
            status_code=400,
            detail="No OTP required for this order"
        )
    
    # Check OTP expiry
    if order.otp_expiry and datetime.utcnow() > order.otp_expiry:
        raise HTTPException(status_code=400, detail="OTP has expired")
    
    # Verify OTP
    if order.delivery_otp != otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    
    # Update order status
    order.status = "delivered"
    order.delivered_at = datetime.utcnow()
    order.payment_status = "completed"
    
    # Add to status history
    if not order.status_history:
        order.status_history = []
    
    order.status_history.append({
        "status": "delivered",
        "timestamp": datetime.utcnow().isoformat(),
        "note": "Delivery verified by customer"
    })
    
    db.commit()
    
    return {
        "success": True,
        "message": "Delivery verified successfully"
    }

@router.post("/{order_id}/reorder")
async def reorder(
    order_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reorder a previous order"""
    original_order = db.query(Order).options(
        joinedload(Order.order_items).joinedload(OrderItem.menu_item)
    ).filter(
        Order.id == order_id,
        Order.customer_id == user.id
    ).first()
    
    if not original_order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Check if service is still active
    service = db.query(Service).filter(
        Service.id == original_order.service_id,
        Service.is_active == True
    ).first()
    
    if not service:
        raise HTTPException(status_code=400, detail="Service is no longer available")
    
    # Prepare items for reorder
    reorder_items = []
    unavailable_items = []
    
    for item in original_order.order_items:
        menu_item = db.query(MenuItem).filter(
            MenuItem.id == item.menu_item_id,
            MenuItem.is_available == True,
            MenuItem.service_id == service.id
        ).first()
        
        if not menu_item:
            unavailable_items.append(item.menu_item.name)
            continue
        
        reorder_items.append({
            "id": menu_item.id,
            "quantity": item.quantity,
            "instructions": item.special_instructions
        })
    
    if unavailable_items:
        return {
            "success": False,
            "message": f"Some items are no longer available: {', '.join(unavailable_items)}",
            "available_items": reorder_items
        }
    
    # Return items data for frontend to create new order
    return {
        "success": True,
        "message": "Ready to reorder",
        "service_id": service.id,
        "items": reorder_items,
        "original_order": {
            "order_number": original_order.order_number,
            "date": original_order.created_at
        }
    }

# =================== TRACK ORDER ===================

@router.get("/{order_id}/track")
async def track_order(
    order_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Track order status and location"""
    order = db.query(Order).options(
        joinedload(Order.service),
        joinedload(Order.team_member)
    ).filter(
        Order.id == order_id,
        Order.customer_id == user.id
    ).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Simulate order tracking stages
    tracking_stages = [
        {"stage": "order_placed", "label": "Order Placed", "active": True, "completed": True},
        {"stage": "order_confirmed", "label": "Order Confirmed", "active": order.status != "pending", "completed": order.status not in ["pending"]},
        {"stage": "food_preparing", "label": "Food Preparing", "active": order.status in ["preparing", "out_for_delivery", "delivered"], "completed": order.status in ["out_for_delivery", "delivered"]},
        {"stage": "out_for_delivery", "label": "Out for Delivery", "active": order.status in ["out_for_delivery", "delivered"], "completed": order.status == "delivered"},
        {"stage": "delivered", "label": "Delivered", "active": order.status == "delivered", "completed": order.status == "delivered"}
    ]
    
    # Calculate time estimates
    time_estimates = {}
    if order.estimated_delivery_time:
        remaining_time = order.estimated_delivery_time - datetime.utcnow()
        if remaining_time.total_seconds() > 0:
            minutes = int(remaining_time.total_seconds() / 60)
            time_estimates["remaining_minutes"] = minutes
            time_estimates["estimated_delivery"] = order.estimated_delivery_time.strftime("%I:%M %p")
    
    return {
        "order": {
            "order_number": order.order_number,
            "status": order.status,
            "current_stage": get_current_stage(order.status),
            "created_at": order.created_at,
            "estimated_delivery": order.estimated_delivery_time
        },
        "service": {
            "name": order.service.name,
            "phone": order.service.phone if hasattr(order.service, 'phone') else None
        },
        "delivery_person": {
            "name": order.team_member.name if order.team_member else None,
            "phone": order.team_member.phone if order.team_member else None
        },
        "tracking": {
            "stages": tracking_stages,
            "time_estimates": time_estimates,
            "last_updated": order.updated_at
        }
    }

# =================== HELPER FUNCTIONS ===================

def is_service_open(service: Service) -> bool:
    """Check if service is currently open"""
    from datetime import datetime
    
    if not service.opening_time or not service.closing_time:
        return True
    
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    
    return service.opening_time <= current_time <= service.closing_time

async def initiate_online_payment(order: Order, payment: Payment):
    """Initiate online payment (placeholder for payment gateway integration)"""
    # This is a placeholder - implement with actual payment gateway
    # Example: Razorpay, Stripe, etc.
    
    # For now, return a mock payment URL
    return f"/api/payment/initiate/{payment.id}"

def get_current_stage(status: str) -> str:
    """Get current tracking stage based on order status"""
    stages = {
        "pending": "order_placed",
        "confirmed": "order_confirmed",
        "preparing": "food_preparing",
        "out_for_delivery": "out_for_delivery",
        "delivered": "delivered",
        "cancelled": "cancelled"
    }
    return stages.get(status, "order_placed")

# =================== ORDER STATISTICS ===================

@router.get("/stats/summary")
async def get_order_summary(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get order summary statistics for user"""
    from sqlalchemy import func
    
    # Total orders
    total_orders = db.query(Order).filter(Order.customer_id == user.id).count()
    
    # Orders by status
    status_counts = db.query(
        Order.status,
        func.count(Order.id).label("count")
    ).filter(Order.customer_id == user.id).group_by(Order.status).all()
    
    # Monthly spending
    current_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_spending = db.query(func.sum(Order.total_amount)).filter(
        Order.customer_id == user.id,
        Order.created_at >= current_month,
        Order.status == "delivered"
    ).scalar() or 0
    
    # Favorite service
    favorite_service = db.query(
        Service.name,
        func.count(Order.id).label("order_count")
    ).join(Order, Order.service_id == Service.id).filter(
        Order.customer_id == user.id
    ).group_by(Service.id, Service.name).order_by(func.count(Order.id).desc()).first()
    
    return {
        "summary": {
            "total_orders": total_orders,
            "monthly_spending": monthly_spending,
            "avg_order_value": monthly_spending / total_orders if total_orders > 0 else 0
        },
        "status_distribution": {status: count for status, count in status_counts},
        "favorite_service": {
            "name": favorite_service[0] if favorite_service else None,
            "order_count": favorite_service[1] if favorite_service else 0
        }
    }