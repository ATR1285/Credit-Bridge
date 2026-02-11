"""
Utility functions for CreditBridge application.
Includes logging, validation, and helper functions.
"""
import logging
import os
import re
from logging.handlers import RotatingFileHandler
from datetime import datetime
from functools import wraps
from flask import session, flash, redirect, url_for


# ============================================================================
# LOGGING UTILITIES
# ============================================================================

def setup_logging(app):
    """
    Configure application logging with file rotation and console output.
    
    Args:
        app: Flask application instance
    """
    # Create logs directory if it doesn't exist
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Get configuration
    log_level = getattr(logging, app.config.get('LOG_LEVEL', 'INFO'))
    log_file = app.config.get('LOG_FILE', 'logs/creditbridge.log')
    max_bytes = app.config.get('LOG_MAX_BYTES', 10 * 1024 * 1024)
    backup_count = app.config.get('LOG_BACKUP_COUNT', 5)
    
    # Create formatter
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
    )
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)
    
    # Console handler for development
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    
    # Configure app logger
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(log_level)
    
    # Log startup
    app.logger.info(f'CreditBridge application started - Environment: {app.config.get("ENV", "development")}')
    
    return app.logger


def log_audit_event(logger, event_type, user_id, details):
    """
    Log audit event with structured format.
    
    Args:
        logger: Logger instance
        event_type: Type of event (LOGIN, ASSESSMENT_CREATE, etc.)
        user_id: ID of user performing action
        details: Additional event details (dict)
    """
    logger.info(f'AUDIT: {event_type} | User: {user_id} | Details: {details}')


def log_error(logger, error, context=None):
    """
    Log error with context information.
    
    Args:
        logger: Logger instance
        error: Exception or error message
        context: Additional context (dict)
    """
    error_msg = f'ERROR: {str(error)}'
    if context:
        error_msg += f' | Context: {context}'
    
    logger.error(error_msg, exc_info=True)


# ============================================================================
# VALIDATION UTILITIES
# ============================================================================

def validate_email(email):
    """
    Validate email address format.
    
    Args:
        email (str): Email address to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not email:
        return False
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_phone(phone):
    """
    Validate Indian phone number.
    
    Args:
        phone (str): Phone number to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not phone:
        return False
    
    # Remove spaces and special characters
    cleaned = re.sub(r'[^\d]', '', phone)
    
    # Should be 10 digits
    return len(cleaned) == 10 and cleaned.isdigit()


def validate_pan(pan):
    """
    Validate PAN card format (Indian tax ID).
    
    Args:
        pan (str): PAN number to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not pan:
        return False
    
    # PAN format: AAAAA9999A (5 letters, 4 digits, 1 letter)
    pattern = r'^[A-Z]{5}[0-9]{4}[A-Z]$'
    return bool(re.match(pattern, pan.upper()))


def validate_password_strength(password):
    """
    Validate password meets security requirements.
    
    Requirements:
    - At least 8 characters
    - Contains uppercase and lowercase
    - Contains at least one digit
    - Contains at least one special character
    
    Args:
        password (str): Password to validate
        
    Returns:
        tuple: (is_valid: bool, error_message: str)
    """
    if not password:
        return False, "Password is required"
    
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r'\d', password):
        return False, "Password must contain at least one digit"
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    
    return True, ""


def sanitize_filename(filename):
    """
    Sanitize filename to prevent directory traversal and injection attacks.
    
    Args:
        filename (str): Original filename
        
    Returns:
        str: Sanitized filename
    """
    # Remove path separators
    filename = filename.replace('/', '_').replace('\\', '_')
    
    # Remove potentially dangerous characters
    filename = re.sub(r'[^\w\s.-]', '', filename)
    
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:255-len(ext)] + ext
    
    return filename


# ============================================================================
# FORMATTING UTILITIES
# ============================================================================

def format_currency(amount, currency='₹'):
    """
    Format number as currency.
    
    Args:
        amount (float): Amount to format
        currency (str): Currency symbol
        
    Returns:
        str: Formatted currency string
    """
    if amount is None:
        return f"{currency}0"
    
    # Indian numbering system (lakhs, crores)
    s = f"{abs(amount):,.2f}"
    parts = s.split('.')
    integer_part = parts[0].replace(',', '')
    decimal_part = parts[1] if len(parts) > 1 else '00'
    
    # Format in Indian style
    if len(integer_part) > 3:
        last_three = integer_part[-3:]
        remaining = integer_part[:-3]
        
        # Add commas every 2 digits for the remaining part
        result = ''
        while len(remaining) > 2:
            result = ',' + remaining[-2:] + result
            remaining = remaining[:-2]
        
        if remaining:
            result = remaining + result
        
        formatted = result + ',' + last_three
    else:
        formatted = integer_part
    
    sign = '-' if amount < 0 else ''
    return f"{sign}{currency}{formatted}.{decimal_part}"


def format_date(dt, format_string='%d %b %Y'):
    """
    Format datetime object to string.
    
    Args:
        dt (datetime): Datetime object
        format_string (str): Format string
        
    Returns:
        str: Formatted date string
    """
    if dt is None:
        return 'N/A'
    
    if isinstance(dt, str):
        return dt
    
    return dt.strftime(format_string)


def format_datetime(dt, format_string='%d %b %Y %I:%M %p'):
    """
    Format datetime object to string with time.
    
    Args:
        dt (datetime): Datetime object
        format_string (str): Format string
        
    Returns:
        str: Formatted datetime string
    """
    if dt is None:
        return 'N/A'
    
    if isinstance(dt, str):
        return dt
    
    return dt.strftime(format_string)


# ============================================================================
# FILE UTILITIES
# ============================================================================

def get_file_size_display(size_bytes):
    """
    Convert bytes to human-readable format.
    
    Args:
        size_bytes (int): File size in bytes
        
    Returns:
        str: Formatted size string
    """
    if size_bytes is None or size_bytes == 0:
        return '0 B'
    
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    unit_index = 0
    size = float(size_bytes)
    
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    return f'{size:.2f} {units[unit_index]}'


def allowed_file(filename, allowed_extensions):
    """
    Check if file extension is allowed.
    
    Args:
        filename (str): Filename to check
        allowed_extensions (set): Set of allowed extensions
        
    Returns:
        bool: True if allowed, False otherwise
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions


# ============================================================================
# SESSION UTILITIES
# ============================================================================

def refresh_session_timeout():
    """
    Refresh session timeout to prevent premature logout.
    Call this on user activity.
    """
    session.modified = True


def clear_flash_messages():
    """
    Clear all flash messages from session.
    """
    session.pop('_flashes', None)


# ============================================================================
# CALCULATION UTILITIES
# ============================================================================

def calculate_percentage(part, total):
    """
    Calculate percentage with safe division.
    
    Args:
        part (float): Part value
        total (float): Total value
        
    Returns:
        float: Percentage (0-100)
    """
    if total == 0:
        return 0.0
    
    return round((part / total) * 100, 2)


def clamp(value, min_value, max_value):
    """
    Clamp value between min and max.
    
    Args:
        value: Value to clamp
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        
    Returns:
        Clamped value
    """
    return max(min_value, min(max_value, value))
