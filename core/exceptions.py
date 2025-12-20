from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.requests import Request
import logging

logger = logging.getLogger(__name__)

class AppException(Exception):
    """Base application exception"""
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)

async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail}
        )
    elif isinstance(exc, AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message}
        )
    
    # Generic error for production
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )
