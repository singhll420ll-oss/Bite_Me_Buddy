# File: api/cart.py
from fastapi import APIRouter, Depends, HTTPException, Form, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
import json

from database import get_db
from models import Cart, MenuItem, Service, User
from auth import get_current_user

router = APIRouter()

@router.get("/")
async def get_cart(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's cart"""
    cart = db.query(Cart).filter(
        Cart.user_id == user.id
    ).first()
    
    if not cart:
        return {
            "success": True,
            "cart": None,
            "message": "Cart is empty"
        }
    
    # Parse cart items
    try:
        items = json.loads(cart.items) if cart.items else []
    except json.JSONDecodeError:
        items = []
    
    # Get service details
    service = db.query(Service).filter(Service.id == cart.service_id).first()
    
    # Enrich cart items with menu item details
    enriched_items = []
    for item in items:
        menu_item = db.query(MenuItem).filter(
            MenuItem.id == item.get("id"),
            MenuItem.is_available == True
        ).first()
        
        if menu_item:
            enriched_items.append({
                "id": menu_item.id,
                "name": menu_item.name,
                "price": menu_item.discounted_price or menu_item.price,
                "original_price": menu_item.price if menu_item.discounted_price else None,
                "image_url": menu_item.image_url,
                "quantity": item.get("quantity", 1),
                "special_instructions": item.get("instructions", ""),
                "is_available": True
            })
        else:
            enriched_items.append({
                "id": item.get("id"),
                "name": "Item no longer available",
                "price": 0,
                "quantity": item.get("quantity", 1),
                "is_available": False
            })
    
    # Calculate totals
    subtotal = sum(item["price"] * item["quantity"] for item in enriched_items if item["is_available"])
    
    # Apply service minimum order amount
    min_order_amount = service.min_order_amount if service else 0
    
    return {
        "success": True,
        "cart": {
            "id": cart.id,
            "service_id": cart.service_id,
            "service_name": service.name if service else None,
            "service_image": service.image_url if service else None,
            "items": enriched_items,
            "subtotal": subtotal,
            "total_amount": cart.total_amount,
            "min_order_amount": min_order_amount,
            "meets_minimum": subtotal >= min_order_amount,
            "created_at": cart.created_at,
            "updated_at": cart.updated_at
        }
    }

@router.post("/add")
async def add_to_cart(
    service_id: int = Form(...),
    item_id: int = Form(...),
    quantity: int = Form(1),
    instructions: Optional[str] = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add item to cart"""
    # Check if menu item exists and is available
    menu_item = db.query(MenuItem).filter(
        MenuItem.id == item_id,
        MenuItem.service_id == service_id,
        MenuItem.is_available == True
    ).first()
    
    if not menu_item:
        raise HTTPException(status_code=404, detail="Menu item not found or unavailable")
    
    # Get or create cart
    cart = db.query(Cart).filter(
        Cart.user_id == user.id,
        Cart.service_id == service_id
    ).first()
    
    if not cart:
        cart = Cart(
            user_id=user.id,
            service_id=service_id,
            items="[]",
            total_amount=0.0
        )
        db.add(cart)
        db.flush()
    
    # Parse current items
    try:
        items = json.loads(cart.items) if cart.items else []
    except json.JSONDecodeError:
        items = []
    
    # Check if item already in cart
    item_found = False
    for item in items:
        if item.get("id") == item_id:
            item["quantity"] = item.get("quantity", 0) + quantity
            item["instructions"] = instructions or item.get("instructions", "")
            item_found = True
            break
    
    # Add new item if not found
    if not item_found:
        items.append({
            "id": item_id,
            "quantity": quantity,
            "instructions": instructions or ""
        })
    
    # Calculate new total
    price = menu_item.discounted_price or menu_item.price
    cart.total_amount += price * quantity
    
    # Update cart
    cart.items = json.dumps(items)
    db.commit()
    
    return {
        "success": True,
        "message": "Item added to cart",
        "cart_id": cart.id,
        "item_count": len(items)
    }

@router.post("/update")
async def update_cart_item(
    item_id: int = Form(...),
    quantity: int = Form(...),
    instructions: Optional[str] = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update cart item quantity"""
    if quantity < 0:
        raise HTTPException(status_code=400, detail="Quantity cannot be negative")
    
    # Find cart containing this item
    cart = db.query(Cart).filter(
        Cart.user_id == user.id
    ).first()
    
    if not cart or not cart.items:
        raise HTTPException(status_code=404, detail="Cart not found")
    
    # Parse items
    try:
        items = json.loads(cart.items)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid cart data")
    
    # Find and update item
    item_found = False
    old_quantity = 0
    
    for item in items:
        if item.get("id") == item_id:
            old_quantity = item.get("quantity", 0)
            if quantity == 0:
                # Remove item if quantity is 0
                items.remove(item)
            else:
                item["quantity"] = quantity
                if instructions is not None:
                    item["instructions"] = instructions
            item_found = True
            break
    
    if not item_found:
        raise HTTPException(status_code=404, detail="Item not found in cart")
    
    # Get menu item price
    menu_item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not menu_item:
        # Item no longer exists, remove from cart
        items = [item for item in items if item.get("id") != item_id]
        price = 0
    else:
        price = menu_item.discounted_price or menu_item.price
    
    # Recalculate total
    cart.total_amount += (quantity - old_quantity) * price
    
    # Update cart
    cart.items = json.dumps(items)
    
    # If cart is empty, delete it
    if not items:
        db.delete(cart)
        db.commit()
        return {
            "success": True,
            "message": "Cart is now empty",
            "cart_empty": True
        }
    
    db.commit()
    
    return {
        "success": True,
        "message": "Cart updated",
        "item_count": len(items)
    }

@router.post("/remove")
async def remove_from_cart(
    item_id: int = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove item from cart"""
    # Find cart containing this item
    cart = db.query(Cart).filter(
        Cart.user_id == user.id
    ).first()
    
    if not cart or not cart.items:
        raise HTTPException(status_code=404, detail="Cart not found")
    
    # Parse items
    try:
        items = json.loads(cart.items)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid cart data")
    
    # Find and remove item
    item_found = False
    removed_quantity = 0
    
    for item in items:
        if item.get("id") == item_id:
            removed_quantity = item.get("quantity", 0)
            items.remove(item)
            item_found = True
            break
    
    if not item_found:
        raise HTTPException(status_code=404, detail="Item not found in cart")
    
    # Get menu item price
    menu_item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    price = menu_item.discounted_price or menu_item.price if menu_item else 0
    
    # Update total
    cart.total_amount -= price * removed_quantity
    
    # Update cart
    cart.items = json.dumps(items)
    
    # If cart is empty, delete it
    if not items:
        db.delete(cart)
        db.commit()
        return {
            "success": True,
            "message": "Cart is now empty",
            "cart_empty": True
        }
    
    db.commit()
    
    return {
        "success": True,
        "message": "Item removed from cart",
        "item_count": len(items)
    }

@router.post("/clear")
async def clear_cart(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Clear entire cart"""
    cart = db.query(Cart).filter(Cart.user_id == user.id).first()
    
    if cart:
        db.delete(cart)
        db.commit()
    
    return {
        "success": True,
        "message": "Cart cleared"
    }

@router.post("/transfer")
async def transfer_cart(
    new_service_id: int = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Transfer cart to a different service"""
    # Get current cart
    current_cart = db.query(Cart).filter(Cart.user_id == user.id).first()
    
    if not current_cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    
    # Check if new service exists
    new_service = db.query(Service).filter(
        Service.id == new_service_id,
        Service.is_active == True
    ).first()
    
    if not new_service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    # Parse current items
    try:
        items = json.loads(current_cart.items) if current_cart.items else []
    except json.JSONDecodeError:
        items = []
    
    # Check if all items are available in new service
    unavailable_items = []
    available_items = []
    
    for item in items:
        menu_item = db.query(MenuItem).filter(
            MenuItem.id == item.get("id"),
            MenuItem.service_id == new_service_id,
            MenuItem.is_available == True
        ).first()
        
        if menu_item:
            available_items.append(item)
        else:
            unavailable_items.append(item.get("id"))
    
    if not available_items:
        raise HTTPException(
            status_code=400,
            detail="None of the cart items are available in the new service"
        )
    
    # Create or update cart for new service
    new_cart = db.query(Cart).filter(
        Cart.user_id == user.id,
        Cart.service_id == new_service_id
    ).first()
    
    if new_cart:
        # Merge with existing cart for new service
        try:
            existing_items = json.loads(new_cart.items) if new_cart.items else []
        except json.JSONDecodeError:
            existing_items = []
        
        # Merge items
        merged_items = existing_items.copy()
        
        for item in available_items:
            # Check if item already exists
            found = False
            for existing_item in merged_items:
                if existing_item.get("id") == item.get("id"):
                    existing_item["quantity"] = existing_item.get("quantity", 0) + item.get("quantity", 1)
                    found = True
                    break
            
            if not found:
                merged_items.append(item)
        
        new_cart.items = json.dumps(merged_items)
        
        # Recalculate total
        total = 0
        for item in merged_items:
            menu_item = db.query(MenuItem).filter(MenuItem.id == item.get("id")).first()
            if menu_item:
                price = menu_item.discounted_price or menu_item.price
                total += price * item.get("quantity", 1)
        
        new_cart.total_amount = total
        
    else:
        # Create new cart
        # Calculate total for available items
        total = 0
        for item in available_items:
            menu_item = db.query(MenuItem).filter(MenuItem.id == item.get("id")).first()
            if menu_item:
                price = menu_item.discounted_price or menu_item.price
                total += price * item.get("quantity", 1)
        
        new_cart = Cart(
            user_id=user.id,
            service_id=new_service_id,
            items=json.dumps(available_items),
            total_amount=total
        )
        db.add(new_cart)
    
    # Delete old cart
    db.delete(current_cart)
    db.commit()
    
    response = {
        "success": True,
        "message": "Cart transferred successfully",
        "new_service": {
            "id": new_service.id,
            "name": new_service.name
        },
        "transferred_items": len(available_items)
    }
    
    if unavailable_items:
        response["warning"] = f"{len(unavailable_items)} items were not available in the new service"
    
    return response

@router.get("/count")
async def get_cart_count(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get cart item count"""
    cart = db.query(Cart).filter(Cart.user_id == user.id).first()
    
    if not cart or not cart.items:
        return {
            "count": 0,
            "has_cart": False
        }
    
    try:
        items = json.loads(cart.items)
        count = sum(item.get("quantity", 1) for item in items)
    except json.JSONDecodeError:
        count = 0
    
    return {
        "count": count,
        "has_cart": True,
        "service_id": cart.service_id
    }