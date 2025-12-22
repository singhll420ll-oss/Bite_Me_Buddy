from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db
from models import User, UserAddress, Order
from auth import get_current_active_user, require_role
from utils import save_upload_file, delete_file

router = APIRouter()

@router.get("/profile")
async def get_profile(
    user: User = Depends(get_current_active_user)
):
    """Get user profile"""
    return {
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "address": user.address,
            "city": user.city,
            "state": user.state,
            "pincode": user.pincode,
            "profile_image": user.profile_image,
            "role": user.role,
            "is_verified": user.is_verified,
            "created_at": user.created_at
        }
    }

@router.put("/profile")
async def update_profile(
    name: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    city: Optional[str] = Form(None),
    state: Optional[str] = Form(None),
    pincode: Optional[str] = Form(None),
    profile_image: Optional[UploadFile] = File(None),
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update user profile"""
    if name:
        user.name = name
    if phone:
        user.phone = phone
    if address:
        user.address = address
    if city:
        user.city = city
    if state:
        user.state = state
    if pincode:
        user.pincode = pincode
    
    # Handle profile image upload
    if profile_image and profile_image.filename:
        # Delete old image if not default
        if user.profile_image and user.profile_image != "/static/images/default-avatar.png":
            delete_file(user.profile_image)
        
        # Save new image
        image_path = save_upload_file(profile_image, "profiles", f"user_{user.id}")
        user.profile_image = image_path
    
    db.commit()
    db.refresh(user)
    
    return {
        "success": True,
        "message": "Profile updated successfully",
        "user": {
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "profile_image": user.profile_image
        }
    }

@router.post("/change-password")
async def change_password(
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Change user password"""
    from auth import AuthHandler
    
    # Verify current password
    if not AuthHandler.verify_password(current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    # Validate new password
    if new_password != confirm_password:
        raise HTTPException(status_code=400, detail="New passwords do not match")
    
    is_valid, message = AuthHandler.validate_password(new_password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=message)
    
    # Update password
    user.password_hash = AuthHandler.get_password_hash(new_password)
    db.commit()
    
    return {
        "success": True,
        "message": "Password changed successfully"
    }

@router.get("/addresses")
async def get_user_addresses(
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user addresses"""
    addresses = db.query(UserAddress).filter(
        UserAddress.user_id == user.id
    ).order_by(UserAddress.is_default.desc(), UserAddress.created_at.desc()).all()
    
    return {
        "addresses": [
            {
                "id": addr.id,
                "label": addr.label,
                "address_line1": addr.address_line1,
                "address_line2": addr.address_line2,
                "city": addr.city,
                "state": addr.state,
                "pincode": addr.pincode,
                "is_default": addr.is_default
            }
            for addr in addresses
        ]
    }

@router.post("/addresses")
async def add_address(
    label: str = Form(...),
    address_line1: str = Form(...),
    address_line2: Optional[str] = Form(None),
    city: str = Form(...),
    state: str = Form(...),
    pincode: str = Form(...),
    is_default: bool = Form(False),
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Add new address"""
    from utils import validate_pincode
    
    if not validate_pincode(pincode):
        raise HTTPException(status_code=400, detail="Invalid pincode")
    
    # If setting as default, unset other defaults
    if is_default:
        db.query(UserAddress).filter(
            UserAddress.user_id == user.id,
            UserAddress.is_default == True
        ).update({"is_default": False})
    
    address = UserAddress(
        user_id=user.id,
        label=label,
        address_line1=address_line1,
        address_line2=address_line2,
        city=city,
        state=state,
        pincode=pincode,
        is_default=is_default
    )
    
    db.add(address)
    db.commit()
    db.refresh(address)
    
    return {
        "success": True,
        "message": "Address added successfully",
        "address": {
            "id": address.id,
            "label": address.label,
            "address_line1": address.address_line1,
            "city": address.city,
            "state": address.state,
            "pincode": address.pincode,
            "is_default": address.is_default
        }
    }

@router.put("/addresses/{address_id}")
async def update_address(
    address_id: int,
    label: Optional[str] = Form(None),
    address_line1: Optional[str] = Form(None),
    address_line2: Optional[str] = Form(None),
    city: Optional[str] = Form(None),
    state: Optional[str] = Form(None),
    pincode: Optional[str] = Form(None),
    is_default: Optional[bool] = Form(None),
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update address"""
    address = db.query(UserAddress).filter(
        UserAddress.id == address_id,
        UserAddress.user_id == user.id
    ).first()
    
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    
    if label:
        address.label = label
    if address_line1:
        address.address_line1 = address_line1
    if address_line2 is not None:
        address.address_line2 = address_line2
    if city:
        address.city = city
    if state:
        address.state = state
    if pincode:
        from utils import validate_pincode
        if not validate_pincode(pincode):
            raise HTTPException(status_code=400, detail="Invalid pincode")
        address.pincode = pincode
    
    # Handle default address
    if is_default and not address.is_default:
        # Unset other defaults
        db.query(UserAddress).filter(
            UserAddress.user_id == user.id,
            UserAddress.is_default == True
        ).update({"is_default": False})
        address.is_default = True
    elif is_default is False:
        address.is_default = False
    
    db.commit()
    db.refresh(address)
    
    return {
        "success": True,
        "message": "Address updated successfully"
    }

@router.delete("/addresses/{address_id}")
async def delete_address(
    address_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete address"""
    address = db.query(UserAddress).filter(
        UserAddress.id == address_id,
        UserAddress.user_id == user.id
    ).first()
    
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    
    # Don't delete if it's the only address
    address_count = db.query(UserAddress).filter(
        UserAddress.user_id == user.id
    ).count()
    
    if address_count <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete the only address")
    
    # If deleting default address, set another as default
    if address.is_default:
        new_default = db.query(UserAddress).filter(
            UserAddress.user_id == user.id,
            UserAddress.id != address_id
        ).first()
        
        if new_default:
            new_default.is_default = True
    
    db.delete(address)
    db.commit()
    
    return {
        "success": True,
        "message": "Address deleted successfully"
    }

@router.get("/orders")
async def get_user_orders(
    page: int = 1,
    limit: int = 10,
    status: Optional[str] = None,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user orders with pagination"""
    from utils import get_pagination_params
    
    offset, limit = get_pagination_params(page, limit)
    
    # Build query
    query = db.query(Order).filter(Order.customer_id == user.id)
    
    if status:
        query = query.filter(Order.status == status)
    
    # Get total count
    total = query.count()
    
    # Get orders
    orders = query.order_by(Order.created_at.desc()).offset(offset).limit(limit).all()
    
    return {
        "orders": [
            {
                "id": order.id,
                "order_number": order.order_number,
                "service_name": order.service.name if order.service else None,
                "total_amount": order.total_amount,
                "status": order.status,
                "created_at": order.created_at,
                "delivered_at": order.delivered_at
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

@router.get("/stats")
async def get_user_stats(
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user statistics"""
    from sqlalchemy import func
    
    # Order stats
    total_orders = db.query(Order).filter(Order.customer_id == user.id).count()
    pending_orders = db.query(Order).filter(
        Order.customer_id == user.id,
        Order.status.in_(["pending", "confirmed", "preparing", "out_for_delivery"])
    ).count()
    
    # Total spent
    total_spent = db.query(func.sum(Order.total_amount)).filter(
        Order.customer_id == user.id,
        Order.status == "delivered"
    ).scalar() or 0
    
    # Recent activity
    recent_orders = db.query(Order).filter(
        Order.customer_id == user.id
    ).order_by(Order.created_at.desc()).limit(5).all()
    
    return {
        "stats": {
            "total_orders": total_orders,
            "pending_orders": pending_orders,
            "total_spent": total_spent,
            "avg_order_value": total_spent / total_orders if total_orders > 0 else 0
        },
        "recent_activity": [
            {
                "order_number": order.order_number,
                "status": order.status,
                "amount": order.total_amount,
                "date": order.created_at
            }
            for order in recent_orders
        ]
      }
