import logging
import sys
from logging.handlers import RotatingFileHandler
import os
from datetime import datetime

def setup_logging():
    """Setup structured logging"""
    
    # Create logs directory if it doesn't exist
    if not os.path.exists("logs"):
        os.makedirs("logs")
    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_format)
    
    # File handler (rotating)
    file_handler = RotatingFileHandler(
        f'logs/app_{datetime.now().strftime("%Y%m")}.log',
        maxBytes=10485760,  # 10MB
        backupCount=10
    )
    file_format = logging.Formatter(
        '{"timestamp": "%(asctime)s", "name": "%(name)s", "level": "%(levelname)s", '
        '"message": "%(message)s", "pathname": "%(pathname)s", "lineno": %(lineno)d}'
    )
    file_handler.setFormatter(file_format)
    
    # Add handlers
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger
