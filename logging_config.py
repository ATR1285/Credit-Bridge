"""
Logging configuration for CreditBridge application.
Sets up structured logging with rotation and proper formatting.
"""

import os
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from datetime import datetime


def setup_logging(app):
    """
    Configure application logging with file and console handlers.
    
    Args:
        app: Flask application instance
    """
    # Create logs directory if it doesn't exist
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    
    # Set log level from config
    log_level = getattr(logging, app.config.get('LOG_LEVEL', 'INFO'))
    app.logger.setLevel(log_level)
    
    # Remove default handlers
    app.logger.handlers.clear()
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s.%(funcName)s (%(pathname)s:%(lineno)d): %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File Handler - Rotating by size
    file_handler = RotatingFileHandler(
        app.config.get('LOG_FILE', 'logs/creditbridge.log'),
        maxBytes=app.config.get('LOG_MAX_BYTES', 10485760),  # 10MB
        backupCount=app.config.get('LOG_BACKUP_COUNT', 5)
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(detailed_formatter)
    app.logger.addHandler(file_handler)
    
    # Error File Handler - Only errors and critical
    error_file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'errors.log'),
        maxBytes=5242880,  # 5MB
        backupCount=5
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(detailed_formatter)
    app.logger.addHandler(error_file_handler)
    
    # Console Handler - Only in development
    if app.debug:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(simple_formatter)
        app.logger.addHandler(console_handler)
    
    # Security Log - For authentication and authorization events
    security_handler = TimedRotatingFileHandler(
        os.path.join(log_dir, 'security.log'),
        when='midnight',
        interval=1,
        backupCount=30  # Keep 30 days
    )
    security_handler.setLevel(logging.WARNING)
    security_handler.setFormatter(detailed_formatter)
    
    # Create security logger
    security_logger = logging.getLogger('security')
    security_logger.setLevel(logging.WARNING)
    security_logger.addHandler(security_handler)
    
    # Access Log - For HTTP requests
    access_handler = TimedRotatingFileHandler(
        os.path.join(log_dir, 'access.log'),
        when='midnight',
        interval=1,
        backupCount=7  # Keep 1 week
    )
    access_handler.setLevel(logging.INFO)
    access_handler.setFormatter(simple_formatter)
    
    access_logger = logging.getLogger('access')
    access_logger.setLevel(logging.INFO)
    access_logger.addHandler(access_handler)
    
    app.logger.info(f"Logging initialized - Level: {logging.getLevelName(log_level)}")
    
    return app.logger


def log_security_event(event_type, details, severity='WARNING'):
    """
    Log security-related events.
    
    Args:
        event_type (str): Type of security event (LOGIN_FAILED, UNAUTHORIZED_ACCESS, etc.)
        details (dict): Event details
        severity (str): Log severity level
    """
    security_logger = logging.getLogger('security')
    
    message = f"[{event_type}] {details}"
    
    if severity == 'CRITICAL':
        security_logger.critical(message)
    elif severity == 'ERROR':
        security_logger.error(message)
    else:
        security_logger.warning(message)


def log_access(request, response_status, user_id=None):
    """
    Log HTTP access.
    
    Args:
        request: Flask request object
        response_status (int): HTTP response status code
        user_id (int, optional): Authenticated user ID
    """
    access_logger = logging.getLogger('access')
    
    message = (
        f"{request.remote_addr} - "
        f"User:{user_id or 'Anonymous'} - "
        f"{request.method} {request.path} - "
        f"Status:{response_status}"
    )
    
    access_logger.info(message)
