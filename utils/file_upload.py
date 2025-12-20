import os
import shutil
import uuid
from typing import Optional
from fastapi import UploadFile, HTTPException
from PIL import Image
import magic

from core.config import settings

async def save_upload_file(upload_file: UploadFile, subdirectory: str = "") -> Optional[str]:
    """
    Save uploaded file and return relative URL
    """
    
    # Validate file size
    upload_file.file.seek(0, 2)  # Seek to end
    file_size = upload_file.file.tell()
    upload_file.file.seek(0)  # Reset to beginning
    
    if file_size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size is {settings.MAX_FILE_SIZE // (1024*1024)}MB"
        )
    
    # Validate file type
    mime_type = magic.from_buffer(upload_file.file.read(2048), mime=True)
    upload_file.file.seek(0)  # Reset to beginning
    
    if mime_type not in settings.ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(settings.ALLOWED_IMAGE_TYPES)}"
        )
    
    # Create upload directory if it doesn't exist
    upload_dir = os.path.join(settings.UPLOAD_DIR, subdirectory)
    os.makedirs(upload_dir, exist_ok=True)
    
    # Generate unique filename
    file_ext = os.path.splitext(upload_file.filename)[1]
    if not file_ext:
        # Default extension based on mime type
        if mime_type == "image/jpeg":
            file_ext = ".jpg"
        elif mime_type == "image/png":
            file_ext = ".png"
        else:
            file_ext = ".bin"
    
    filename = f"{uuid.uuid4().hex}{file_ext}"
    file_path = os.path.join(upload_dir, filename)
    
    try:
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
        
        # Optimize image if it's an image
        if mime_type.startswith("image/"):
            optimize_image(file_path)
        
        # Return relative URL
        relative_path = os.path.join("uploads", subdirectory, filename).replace("\\", "/")
        return relative_path
        
    except Exception as e:
        # Clean up if error occurs
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

def optimize_image(file_path: str, max_size: tuple = (800, 800)) -> None:
    """
    Optimize image size and quality
    """
    try:
        with Image.open(file_path) as img:
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = rgb_img
            
            # Resize if too large
            if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Save optimized image
            img.save(file_path, "JPEG" if file_path.lower().endswith(('.jpg', '.jpeg')) else "PNG", 
                    quality=85, optimize=True)
    except Exception as e:
        # If optimization fails, keep original
        pass

def delete_file(file_url: str) -> bool:
    """
    Delete file from filesystem
    """
    if not file_url:
        return False
    
    # Convert URL to file path
    if file_url.startswith("uploads/"):
        file_path = os.path.join("static", file_url)
    else:
        file_path = os.path.join("static", "uploads", file_url)
    
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
    except Exception:
        pass
    
    return False
