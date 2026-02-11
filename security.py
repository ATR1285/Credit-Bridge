"""
Security utilities for CreditBridge application.
Password validation, secure session management, and input sanitization.
"""
import re
import secrets
import string
from werkzeug.security import generate_password_hash, check_password_hash


# ============================================================================
# PASSWORD UTILITIES
# ============================================================================

def validate_password_strength(password):
    """
    Validate password meets security requirements.
    
    Requirements:
    - At least 8 characters
    - Contains uppercase and lowercase letters
    - Contains at least one digit
    - Contains at least one special character
    
    Args:
        password (str): Password to validate
        
    Returns:
        tuple: (is_valid: bool, error_message: str or None)
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
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\;/]', password):
        return False, "Password must contain at least one special character (!@#$%^&*...)"
    
    # Check for common passwords
    common_passwords = [
        'password', '12345678', 'qwerty', 'abc123', 'password123',
        'admin123', 'letmein', 'welcome', 'monkey', 'dragon'
    ]
    if password.lower() in common_passwords:
        return False, "Password is too common. Please choose a stronger password"
    
    return True, None


def generate_secure_password(length=16):
    """
    Generate a cryptographically secure random password.
    
    Args:
        length (int): Password length (default: 16)
        
    Returns:
        str: Secure random password
    """
    alphabet = string.ascii_letters + string.digits + string.punctuation
    
    # Ensure at least one of each required character type
    password = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice(string.punctuation)
    ]
    
    # Fill the rest randomly
    password.extend(secrets.choice(alphabet) for _ in range(length - 4))
    
    # Shuffle to avoid predictable pattern
    secrets.SystemRandom().shuffle(password)
    
    return ''.join(password)


def hash_password(password):
    """
    Hash password using werkzeug's secure method.
    
    Args:
        password (str): Plain text password
        
    Returns:
        str: Hashed password
    """
    return generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)


def verify_password(password, password_hash):
    """
    Verify password against hash.
    
    Args:
        password (str): Plain text password
        password_hash (str): Hashed password
        
    Returns:
        bool: True if password matches, False otherwise
    """
    return check_password_hash(password_hash, password)


# ============================================================================
# INPUT SANITIZATION
# ============================================================================

def sanitize_input(text, max_length=None):
    """
    Sanitize user input to prevent injection attacks.
    
    Args:
        text (str): Input text
        max_length (int, optional): Maximum allowed length
        
    Returns:
        str: Sanitized text
    """
    if not text:
        return ""
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Remove control characters except newline and tab
    text = ''.join(char for char in text if char == '\n' or char == '\t' or ord(char) >= 32)
    
    # Trim whitespace
    text = text.strip()
    
    # Enforce max length if specified
    if max_length and len(text) > max_length:
        text = text[:max_length]
    
    return text


def sanitize_filename(filename):
    """
    Sanitize filename to prevent path traversal attacks.
    
    Args:
        filename (str): Original filename
        
    Returns:
        str: Safe filename
    """
    if not filename:
        return "unnamed"
    
    # Remove path separators
    filename = filename.replace('/', '_').replace('\\', '_')
    
    # Remove potentially dangerous characters
    filename = re.sub(r'[^\w\s.-]', '', filename)
    
    # Remove leading dots and spaces
    filename = filename.lstrip('. ')
    
    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        max_name_length = 255 - len(ext) - 1
        filename = name[:max_name_length] + ('.' + ext if ext else '')
    
    # Default if empty after sanitization
    if not filename:
        filename = "unnamed"
    
    return filename


def sanitize_sql_like_pattern(pattern):
    """
    Escape special characters in SQL LIKE pattern.
    
    Args:
        pattern (str): Search pattern
        
    Returns:
        str: Escaped pattern
    """
    if not pattern:
        return ""
    
    # Escape SQL LIKE special characters
    pattern = pattern.replace('\\', '\\\\')
    pattern = pattern.replace('%', '\\%')
    pattern = pattern.replace('_', '\\_')
    
    return pattern


# ============================================================================
# SESSION SECURITY
# ============================================================================

def generate_session_token():
    """
    Generate a secure session token.
    
    Returns:
        str: Random session token
    """
    return secrets.token_urlsafe(32)


def generate_csrf_token():
    """
    Generate a CSRF token.
    
    Returns:
        str: CSRF token
    """
    return secrets.token_hex(32)


# ============================================================================
# DATA VALIDATION
# ============================================================================

def validate_email(email):
    """
    Validate email address format.
    
    Args:
        email (str): Email address
        
    Returns:
        bool: True if valid email format
    """
    if not email:
        return False
    
    # RFC 5322 simplified pattern
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(pattern, email):
        return False
    
    # Additional checks
    if len(email) > 320:  # Max email length per RFC
        return False
    
    local, domain = email.rsplit('@', 1)
    
    if len(local) > 64:  # Max local part length
        return False
    
    if len(domain) > 255:  # Max domain length
        return False
    
    return True


def validate_phone_number(phone):
    """
    Validate Indian phone number.
    
    Args:
        phone (str): Phone number
        
    Returns:
        bool: True if valid phone number
    """
    if not phone:
        return False
    
    # Remove all non-digit characters
    digits = re.sub(r'\D', '', phone)
    
    # Indian phone numbers are 10 digits
    if len(digits) != 10:
        return False
    
    # Should start with 6, 7, 8, or 9
    if digits[0] not in '6789':
        return False
    
    return True


def validate_pan_card(pan):
    """
    Validate Indian PAN card number format.
    
    Args:
        pan (str): PAN number
        
    Returns:
        bool: True if valid PAN format
    """
    if not pan:
        return False
    
    # PAN format: AAAAA9999A
    # 5 letters, 4 numbers, 1 letter
    pattern = r'^[A-Z]{5}[0-9]{4}[A-Z]$'
    
    return bool(re.match(pattern, pan.upper()))


def validate_aadhaar_number(aadhaar):
    """
    Validate Indian Aadhaar number format.
    
    Args:
        aadhaar (str): Aadhaar number
        
    Returns:
        bool: True if valid Aadhaar format
    """
    if not aadhaar:
        return False
    
    # Remove spaces and special characters
    digits = re.sub(r'\D', '', aadhaar)
    
    # Aadhaar is 12 digits
    if len(digits) != 12:
        return False
    
    # Should not start with 0 or 1
    if digits[0] in '01':
        return False
    
    return True


def validate_amount(amount, min_value=0, max_value=None):
    """
    Validate monetary amount.
    
    Args:
        amount: Amount to validate
        min_value (float): Minimum allowed value
        max_value (float, optional): Maximum allowed value
        
    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return False, "Invalid amount format"
    
    if amount < min_value:
        return False, f"Amount must be at least {min_value}"
    
    if max_value is not None and amount > max_value:
        return False, f"Amount cannot exceed {max_value}"
    
    # Check for reasonable decimal places (max 2 for currency)
    if round(amount, 2) != amount:
        return False, "Amount can have at most 2 decimal places"
    
    return True, None


# ============================================================================
# RATE LIMITING HELPERS
# ============================================================================

def generate_rate_limit_key(identifier, action):
    """
    Generate a key for rate limiting.
    
    Args:
        identifier (str): User identifier (IP, user ID, etc.)
        action (str): Action being rate limited
        
    Returns:
        str: Rate limit key
    """
    return f"ratelimit:{action}:{identifier}"


# ============================================================================
# SECURE RANDOM UTILITIES
# ============================================================================

def generate_verification_code(length=6):
    """
    Generate a numeric verification code.
    
    Args:
        length (int): Code length (default: 6)
        
    Returns:
        str: Verification code
    """
    return ''.join(secrets.choice(string.digits) for _ in range(length))


def generate_api_key(prefix='sk_'):
    """
    Generate a secure API key.
    
    Args:
        prefix (str): Key prefix
        
    Returns:
        str: API key
    """
    random_part = secrets.token_urlsafe(32)
    return f"{prefix}{random_part}"
