from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from database import get_db
from crud.service import (
    get_all_services, get_service_by_id, create_service,
    update_service, delete_service, create_menu_item,
    get_menu_items_by_service, update_menu_item, delete_menu_item,
    get_menu_item_by_id
)
from core.security import get_current_user
from utils.file_upload import save_upload_file

router = APIRouter(tags=["services"])
templates = Jinja2Templates(directory="templates")

@router.get("/services", response_class=HTMLResponse)
async def services_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Services list page"""
    
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    
    services = await get_all_services(db)
    
    return templates.TemplateResponse(
        "services.html",
        {
            "request": request,
            "services": services,
            "current_user": current_user
        }
    )

@router.get("/services/{service_id}", response_class=HTMLResponse)
async def service_menu(
    request: Request,
    service_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Service menu page"""
    
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    
    service = await get_service_by_id(db, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    menu_items = await get_menu_items_by_service(db, service_id)
    
    return templates.TemplateResponse(
        "service_menu.html",
        {
            "request": request,
            "service": service,
            "menu_items": menu_items,
            "current_user": current_user
        }
    )

@router.get("/admin/services", response_class=HTMLResponse)
async def admin_services_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Admin services management page"""
    
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    services = await get_all_services(db, limit=1000)
    
    return templates.TemplateResponse(
        "admin_services.html",
        {
            "request": request,
            "services": services,
            "current_user": current_user
        }
    )

@router.post("/admin/services")
async def admin_create_service(
    request: Request,
    name: str = Form(...),
    description: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create new service (Admin only)"""
    
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    service = await create_service(db, name, description)
    
    # HTMX response
    return templates.TemplateResponse(
        "partials/service_item.html",
        {
            "request": request,
            "service": service
        }
    )

@router.put("/admin/services/{service_id}")
async def admin_update_service(
    request: Request,
    service_id: int,
    name: str = Form(...),
    description: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update service (Admin only)"""
    
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    update_data = {"name": name, "description": description}
    service = await update_service(db, service_id, update_data)
    
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    return templates.TemplateResponse(
        "partials/service_item.html",
        {
            "request": request,
            "service": service
        }
    )

@router.delete("/admin/services/{service_id}")
async def admin_delete_service(
    service_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete service (Admin only)"""
    
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    success = await delete_service(db, service_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Service not found")
    
    return {"message": "Service deleted successfully"}

@router.get("/admin/services/{service_id}/menu")
async def admin_service_menu_items(
    request: Request,
    service_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get menu items for a service (Admin)"""
    
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    menu_items = await get_menu_items_by_service(db, service_id)
    
    return templates.TemplateResponse(
        "partials/menu_items_list.html",
        {
            "request": request,
            "menu_items": menu_items,
            "service_id": service_id
        }
    )

@router.post("/admin/services/{service_id}/menu")
async def admin_create_menu_item(
    request: Request,
    service_id: int,
    name: str = Form(...),
    description: Optional[str] = Form(None),
    price: float = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create new menu item (Admin only)"""
    
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    menu_item = await create_menu_item(db, service_id, name, description, price)
    
    return templates.TemplateResponse(
        "partials/menu_item.html",
        {
            "request": request,
            "item": menu_item
        }
    )

@router.put("/admin/menu/{item_id}")
async def admin_update_menu_item(
    request: Request,
    item_id: int,
    name: str = Form(...),
    description: Optional[str] = Form(None),
    price: float = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update menu item (Admin only)"""
    
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    update_data = {"name": name, "description": description, "price": price}
    menu_item = await update_menu_item(db, item_id, update_data)
    
    if not menu_item:
        raise HTTPException(status_code=404, detail="Menu item not found")
    
    return templates.TemplateResponse(
        "partials/menu_item.html",
        {
            "request": request,
            "item": menu_item
        }
    )

@router.delete("/admin/menu/{item_id}")
async def admin_delete_menu_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete menu item (Admin only)"""
    
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    success = await delete_menu_item(db, item_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Menu item not found")
    
    return {"message": "Menu item deleted successfully"}
