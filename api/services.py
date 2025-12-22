# File: api/services.py
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc, or_
from typing import List, Optional
import math

from database import get_db
from models import Service, MenuItem, Category, ServiceCategory, Review
from auth import get_current_user, require_role
from utils import save_upload_file, delete_file, slugify, get_pagination_params
from config import settings

router = APIRouter()

# =================== PUBLIC ENDPOINTS ===================

@router.get("/")
async def get_services(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("name", regex="^(name|rating|created_at)$"),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),
    is_featured: Optional[bool] = Query(None),
    db: Session = Depends(get_db)
):
    """Get all active services with filters"""
    offset, limit = get_pagination_params(page, limit)
    
    # Build query
    query = db.query(Service).filter(Service.is_active == True)
    
    # Apply filters
    if category:
        query = query.join(ServiceCategory).join(Category).filter(
            Category.slug == category
        )
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Service.name.ilike(search_term),
                Service.description.ilike(search_term),
                Service.short_description.ilike(search_term)
            )
        )
    
    if is_featured is not None:
        query = query.filter(Service.is_featured == is_featured)
    
    # Apply sorting
    if sort_by == "rating":
        order_by = desc(Service.rating) if sort_order == "desc" else Service.rating
    elif sort_by == "created_at":
        order_by = desc(Service.created_at) if sort_order == "desc" else Service.created_at
    else:
        order_by = desc(Service.name) if sort_order == "desc" else Service.name
    
    # Get total count
    total = query.count()
    
    # Get services
    services = query.order_by(order_by).offset(offset).limit(limit).all()
    
    return {
        "services": [
            {
                "id": service.id,
                "name": service.name,
                "slug": service.slug,
                "description": service.short_description or service.description,
                "image_url": service.image_url,
                "rating": service.rating,
                "total_reviews": service.total_reviews,
                "preparation_time": service.preparation_time,
                "delivery_fee": service.delivery_fee,
                "min_order_amount": service.min_order_amount,
                "is_featured": service.is_featured,
                "opening_time": service.opening_time,
                "closing_time": service.closing_time,
                "categories": [cat.name for cat in service.categories]
            }
            for service in services
        ],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": math.ceil(total / limit) if limit > 0 else 0
        }
    }

@router.get("/featured")
async def get_featured_services(
    limit: int = Query(6, ge=1, le=20),
    db: Session = Depends(get_db)
):
    """Get featured services"""
    services = db.query(Service).filter(
        Service.is_active == True,
        Service.is_featured == True
    ).order_by(desc(Service.rating)).limit(limit).all()
    
    return {
        "services": [
            {
                "id": service.id,
                "name": service.name,
                "slug": service.slug,
                "image_url": service.image_url,
                "rating": service.rating,
                "delivery_fee": service.delivery_fee,
                "preparation_time": service.preparation_time
            }
            for service in services
        ]
    }

@router.get("/{service_id_or_slug}")
async def get_service_details(
    service_id_or_slug: str,
    db: Session = Depends(get_db)
):
    """Get service details by ID or slug"""
    try:
        service_id = int(service_id_or_slug)
        service = db.query(Service).filter(
            Service.id == service_id,
            Service.is_active == True
        ).first()
    except ValueError:
        service = db.query(Service).filter(
            Service.slug == service_id_or_slug,
            Service.is_active == True
        ).first()
    
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    # Get menu items with categories
    menu_items = db.query(MenuItem).filter(
        MenuItem.service_id == service.id,
        MenuItem.is_available == True
    ).options(joinedload(MenuItem.category)).all()
    
    # Get categories
    categories = db.query(Category).join(ServiceCategory).filter(
        ServiceCategory.service_id == service.id,
        Category.is_active == True
    ).all()
    
    # Get recent reviews
    reviews = db.query(Review).filter(
        Review.service_id == service.id,
        Review.is_approved == True
    ).order_by(desc(Review.created_at)).limit(5).all()
    
    # Calculate rating distribution
    rating_dist = db.query(
        Review.rating,
        func.count(Review.id).label("count")
    ).filter(
        Review.service_id == service.id,
        Review.is_approved == True
    ).group_by(Review.rating).order_by(Review.rating).all()
    
    rating_distribution = {str(rating): count for rating, count in rating_dist}
    
    return {
        "service": {
            "id": service.id,
            "name": service.name,
            "slug": service.slug,
            "description": service.description,
            "short_description": service.short_description,
            "image_url": service.image_url,
            "banner_image": service.banner_image,
            "rating": service.rating,
            "total_reviews": service.total_reviews,
            "preparation_time": service.preparation_time,
            "delivery_fee": service.delivery_fee,
            "min_order_amount": service.min_order_amount,
            "opening_time": service.opening_time,
            "closing_time": service.closing_time,
            "is_open": is_service_open(service),
            "categories": [{"id": cat.id, "name": cat.name} for cat in categories]
        },
        "menu_items": [
            {
                "id": item.id,
                "name": item.name,
                "slug": item.slug,
                "description": item.short_description or item.description,
                "price": item.price,
                "discounted_price": item.discounted_price,
                "image_url": item.image_url,
                "is_vegetarian": item.is_vegetarian,
                "is_spicy": item.is_spicy,
                "category": item.category.name if item.category else None,
                "preparation_time": item.preparation_time
            }
            for item in menu_items
        ],
        "reviews": {
            "average": service.rating,
            "total": service.total_reviews,
            "distribution": rating_distribution,
            "recent": [
                {
                    "user_name": review.user.name,
                    "rating": review.rating,
                    "comment": review.comment,
                    "created_at": review.created_at,
                    "menu_item": review.menu_item.name if review.menu_item else None
                }
                for review in reviews
            ]
        }
    }

@router.get("/{service_id}/menu")
async def get_service_menu(
    service_id: int,
    category: Optional[str] = Query(None),
    vegetarian_only: bool = Query(False),
    db: Session = Depends(get_db)
):
    """Get service menu with filters"""
    service = db.query(Service).filter(
        Service.id == service_id,
        Service.is_active == True
    ).first()
    
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    # Build query
    query = db.query(MenuItem).filter(
        MenuItem.service_id == service_id,
        MenuItem.is_available == True
    )
    
    # Apply filters
    if category:
        query = query.join(Category).filter(Category.slug == category)
    
    if vegetarian_only:
        query = query.filter(MenuItem.is_vegetarian == True)
    
    menu_items = query.order_by(
        MenuItem.display_order,
        MenuItem.name
    ).all()
    
    # Get categories for this service
    categories = db.query(Category).join(
        MenuItem, MenuItem.category_id == Category.id
    ).filter(
        MenuItem.service_id == service_id,
        MenuItem.is_available == True,
        Category.is_active == True
    ).distinct().order_by(Category.name).all()
    
    return {
        "service": {
            "id": service.id,
            "name": service.name
        },
        "categories": [
            {
                "id": cat.id,
                "name": cat.name,
                "slug": cat.slug
            }
            for cat in categories
        ],
        "menu_items": [
            {
                "id": item.id,
                "name": item.name,
                "description": item.short_description or item.description,
                "price": item.price,
                "discounted_price": item.discounted_price,
                "image_url": item.image_url,
                "is_vegetarian": item.is_vegetarian,
                "is_spicy": item.is_spicy,
                "category": item.category.name if item.category else None,
                "category_slug": item.category.slug if item.category else None,
                "ingredients": item.ingredients,
                "calories": item.calories,
                "preparation_time": item.preparation_time,
                "is_featured": item.is_featured
            }
            for item in menu_items
        ]
    }

@router.get("/{service_id}/categories")
async def get_service_categories(
    service_id: int,
    db: Session = Depends(get_db)
):
    """Get categories for a service"""
    categories = db.query(Category).join(ServiceCategory).filter(
        ServiceCategory.service_id == service_id,
        Category.is_active == True
    ).order_by(Category.name).all()
    
    return {
        "categories": [
            {
                "id": cat.id,
                "name": cat.name,
                "slug": cat.slug,
                "description": cat.description,
                "image_url": cat.image_url
            }
            for cat in categories
        ]
    }

# =================== HELPER FUNCTIONS ===================

def is_service_open(service: Service) -> bool:
    """Check if service is currently open"""
    from datetime import datetime
    
    if not service.opening_time or not service.closing_time:
        return True
    
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    
    # Simple time comparison
    return service.opening_time <= current_time <= service.closing_time

# =================== ADMIN ENDPOINTS ===================

@router.post("/", dependencies=[Depends(require_role("admin"))])
async def create_service(
    name: str = Form(...),
    description: str = Form(...),
    short_description: Optional[str] = Form(None),
    preparation_time: int = Form(30),
    delivery_fee: float = Form(20.0),
    min_order_amount: float = Form(0.0),
    opening_time: str = Form("09:00"),
    closing_time: str = Form("23:00"),
    is_featured: bool = Form(False),
    image: Optional[UploadFile] = File(None),
    banner_image: Optional[UploadFile] = File(None),
    category_ids: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Create new service (Admin only)"""
    # Check if service with same name exists
    existing = db.query(Service).filter(Service.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Service with this name already exists")
    
    # Create slug from name
    slug = slugify(name)
    
    # Create service
    service = Service(
        name=name,
        slug=slug,
        description=description,
        short_description=short_description,
        preparation_time=preparation_time,
        delivery_fee=delivery_fee,
        min_order_amount=min_order_amount,
        opening_time=opening_time,
        closing_time=closing_time,
        is_featured=is_featured
    )
    
    # Handle image uploads
    if image and image.filename:
        image_path = save_upload_file(image, "services", "service")
        service.image_url = image_path
    
    if banner_image and banner_image.filename:
        banner_path = save_upload_file(banner_image, "services", "banner")
        service.banner_image = banner_path
    
    db.add(service)
    db.flush()  # Get service ID
    
    # Add categories
    if category_ids:
        try:
            cat_ids = [int(cid) for cid in category_ids.split(",")]
            categories = db.query(Category).filter(Category.id.in_(cat_ids)).all()
            
            for category in categories:
                service_category = ServiceCategory(
                    service_id=service.id,
                    category_id=category.id
                )
                db.add(service_category)
        except (ValueError, AttributeError):
            pass
    
    db.commit()
    db.refresh(service)
    
    return {
        "success": True,
        "message": "Service created successfully",
        "service": {
            "id": service.id,
            "name": service.name,
            "slug": service.slug
        }
    }

@router.put("/{service_id}", dependencies=[Depends(require_role("admin"))])
async def update_service(
    service_id: int,
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    short_description: Optional[str] = Form(None),
    preparation_time: Optional[int] = Form(None),
    delivery_fee: Optional[float] = Form(None),
    min_order_amount: Optional[float] = Form(None),
    opening_time: Optional[str] = Form(None),
    closing_time: Optional[str] = Form(None),
    is_featured: Optional[bool] = Form(None),
    is_active: Optional[bool] = Form(None),
    image: Optional[UploadFile] = File(None),
    banner_image: Optional[UploadFile] = File(None),
    category_ids: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Update service (Admin only)"""
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    # Update fields
    if name is not None and name != service.name:
        # Check if new name already exists
        existing = db.query(Service).filter(
            Service.name == name,
            Service.id != service_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Service with this name already exists")
        
        service.name = name
        service.slug = slugify(name)
    
    if description is not None:
        service.description = description
    
    if short_description is not None:
        service.short_description = short_description
    
    if preparation_time is not None:
        service.preparation_time = preparation_time
    
    if delivery_fee is not None:
        service.delivery_fee = delivery_fee
    
    if min_order_amount is not None:
        service.min_order_amount = min_order_amount
    
    if opening_time is not None:
        service.opening_time = opening_time
    
    if closing_time is not None:
        service.closing_time = closing_time
    
    if is_featured is not None:
        service.is_featured = is_featured
    
    if is_active is not None:
        service.is_active = is_active
    
    # Handle image uploads
    if image and image.filename:
        # Delete old image if exists
        if service.image_url and service.image_url != "/static/images/default-service.jpg":
            delete_file(service.image_url)
        
        # Save new image
        image_path = save_upload_file(image, "services", f"service_{service.id}")
        service.image_url = image_path
    
    if banner_image and banner_image.filename:
        # Delete old banner if exists
        if service.banner_image:
            delete_file(service.banner_image)
        
        # Save new banner
        banner_path = save_upload_file(banner_image, "services", f"banner_{service.id}")
        service.banner_image = banner_path
    
    # Update categories
    if category_ids is not None:
        # Remove existing categories
        db.query(ServiceCategory).filter(
            ServiceCategory.service_id == service_id
        ).delete()
        
        # Add new categories
        if category_ids:
            try:
                cat_ids = [int(cid) for cid in category_ids.split(",")]
                categories = db.query(Category).filter(Category.id.in_(cat_ids)).all()
                
                for category in categories:
                    service_category = ServiceCategory(
                        service_id=service.id,
                        category_id=category.id
                    )
                    db.add(service_category)
            except (ValueError, AttributeError):
                pass
    
    db.commit()
    db.refresh(service)
    
    return {
        "success": True,
        "message": "Service updated successfully",
        "service": {
            "id": service.id,
            "name": service.name,
            "is_active": service.is_active
        }
    }

@router.delete("/{service_id}", dependencies=[Depends(require_role("admin"))])
async def delete_service(
    service_id: int,
    db: Session = Depends(get_db)
):
    """Delete service (Admin only) - Soft delete"""
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    # Check if service has active orders
    from models import Order
    active_orders = db.query(Order).filter(
        Order.service_id == service_id,
        Order.status.in_(["pending", "confirmed", "preparing", "out_for_delivery"])
    ).count()
    
    if active_orders > 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete service with active orders"
        )
    
    # Soft delete
    service.is_active = False
    db.commit()
    
    return {
        "success": True,
        "message": "Service deleted successfully"
    }

@router.get("/{service_id}/stats", dependencies=[Depends(require_role("admin"))])
async def get_service_stats(
    service_id: int,
    period: str = Query("month", regex="^(day|week|month|year)$"),
    db: Session = Depends(get_db)
):
    """Get service statistics (Admin only)"""
    from sqlalchemy import func, extract
    from datetime import datetime, timedelta
    
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    # Calculate date range
    now = datetime.utcnow()
    
    if period == "day":
        start_date = now - timedelta(days=1)
        date_format = "%H:00"
        group_by = extract('hour', Order.created_at)
    elif period == "week":
        start_date = now - timedelta(days=7)
        date_format = "%a"
        group_by = func.date(Order.created_at)
    elif period == "month":
        start_date = now - timedelta(days=30)
        date_format = "%d %b"
        group_by = func.date(Order.created_at)
    else:  # year
        start_date = now - timedelta(days=365)
        date_format = "%b %Y"
        group_by = func.concat(
            func.extract('year', Order.created_at),
            '-',
            func.extract('month', Order.created_at)
        )
    
    # Get order statistics
    orders = db.query(
        group_by.label("date_group"),
        func.count(Order.id).label("order_count"),
        func.sum(Order.total_amount).label("revenue")
    ).filter(
        Order.service_id == service_id,
        Order.created_at >= start_date,
        Order.status == "delivered"
    ).group_by(group_by).order_by(group_by).all()
    
    # Get recent orders
    recent_orders = db.query(Order).filter(
        Order.service_id == service_id
    ).order_by(desc(Order.created_at)).limit(10).all()
    
    # Calculate totals
    total_orders = db.query(Order).filter(Order.service_id == service_id).count()
    total_revenue = db.query(func.sum(Order.total_amount)).filter(
        Order.service_id == service_id,
        Order.status == "delivered"
    ).scalar() or 0
    
    avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
    
    return {
        "service": {
            "id": service.id,
            "name": service.name,
            "total_orders": total_orders,
            "total_revenue": total_revenue,
            "avg_order_value": avg_order_value,
            "rating": service.rating,
            "total_reviews": service.total_reviews
        },
        "analytics": {
            "period": period,
            "data": [
                {
                    "date": row.date_group,
                    "orders": row.order_count,
                    "revenue": row.revenue or 0
                }
                for row in orders
            ]
        },
        "recent_orders": [
            {
                "order_number": order.order_number,
                "customer": order.customer.name,
                "total": order.total_amount,
                "status": order.status,
                "created_at": order.created_at
            }
            for order in recent_orders
        ]
    }
