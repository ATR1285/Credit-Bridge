"""
Input validation utilities for CreditBridge.
Provides validation functions for all form inputs.
"""

import re
from datetime import datetime


class ValidationError(Exception):
    """Custom validation error."""
    pass


def validate_required(value, field_name):
    """
    Validate that a field is not empty.
    
    Args:
        value: Field value
        field_name (str): Name of field for error message
        
    Raises:
        ValidationError: If field is empty
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{field_name} is required")


def validate_email(email):
    """
    Validate email format.
    
    Args:
        email (str): Email address
        
    Returns:
        bool: True if valid
        
    Raises:
        ValidationError: If email is invalid
    """
    if not email:
        return True  # Optional field
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        raise ValidationError("Invalid email format")
    
    return True


def validate_phone(phone):
    """
    Validate Indian phone number.
    
    Args:
        phone (str): Phone number
        
    Returns:
        bool: True if valid
        
    Raises:
        ValidationError: If phone is invalid
    """
    validate_required(phone, "Phone number")
    
    # Remove spaces and common separators
    clean_phone = re.sub(r'[\s\-\(\)]', '', phone)
    
    # Check for Indian mobile pattern (10 digits starting with 6-9)
    if not re.match(r'^[6-9]\d{9}$', clean_phone):
        raise ValidationError("Invalid phone number. Must be 10 digits starting with 6-9")
    
    return True


def validate_pan(pan):
    """
    Validate PAN card format.
    
    Args:
        pan (str): PAN card number
        
    Returns:
        bool: True if valid
        
    Raises:
        ValidationError: If PAN is invalid
    """
    if not pan:
        return True  # Optional field
    
    pan = pan.upper().strip()
    
    # PAN format: AAAAA9999A (5 letters, 4 numbers, 1 letter)
    if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', pan):
        raise ValidationError("Invalid PAN format. Must be AAAAA9999A")
    
    return True


def validate_aadhaar(aadhaar):
    """
    Validate Aadhaar number.
    
    Args:
        aadhaar (str): Aadhaar number
        
    Returns:
        bool: True if valid
        
    Raises:
        ValidationError: If Aadhaar is invalid
    """
    if not aadhaar:
        return True  # Optional field
    
    # Remove spaces
    clean_aadhaar = re.sub(r'\s', '', aadhaar)
    
    # Aadhaar is 12 digits
    if not re.match(r'^\d{12}$', clean_aadhaar):
        raise ValidationError("Invalid Aadhaar number. Must be 12 digits")
    
    return True


def validate_amount(amount, field_name, min_value=0, max_value=None):
    """
    Validate monetary amount.
    
    Args:
        amount: Amount value
        field_name (str): Name of field
        min_value (float): Minimum allowed value
        max_value (float, optional): Maximum allowed value
        
    Returns:
        float: Validated amount
        
    Raises:
        ValidationError: If amount is invalid
    """
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        raise ValidationError(f"{field_name} must be a valid number")
    
    if amount < min_value:
        raise ValidationError(f"{field_name} must be at least ₹{min_value:,.2f}")
    
    if max_value is not None and amount > max_value:
        raise ValidationError(f"{field_name} cannot exceed ₹{max_value:,.2f}")
    
    return amount


def validate_income(income):
    """
    Validate monthly income.
    
    Args:
        income: Income value
        
    Returns:
        float: Validated income
        
    Raises:
        ValidationError: If income is invalid
    """
    return validate_amount(income, "Monthly income", min_value=0, max_value=10000000)


def validate_expenses(expenses, income):
    """
    Validate monthly expenses.
    
    Args:
        expenses: Expenses value
        income: Monthly income for comparison
        
    Returns:
        float: Validated expenses
        
    Raises:
        ValidationError: If expenses are invalid
    """
    expenses = validate_amount(expenses, "Monthly expenses", min_value=0)
    
    if expenses > income * 1.5:
        raise ValidationError("Monthly expenses seem unusually high compared to income")
    
    return expenses


def validate_integer(value, field_name, min_value=0, max_value=None):
    """
    Validate integer value.
    
    Args:
        value: Integer value
        field_name (str): Name of field
        min_value (int): Minimum allowed value
        max_value (int, optional): Maximum allowed value
        
    Returns:
        int: Validated integer
        
    Raises:
        ValidationError: If value is invalid
    """
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field_name} must be a whole number")
    
    if value < min_value:
        raise ValidationError(f"{field_name} must be at least {min_value}")
    
    if max_value is not None and value > max_value:
        raise ValidationError(f"{field_name} cannot exceed {max_value}")
    
    return value


def validate_assessment_data(form_data):
    """
    Validate complete assessment form data.
    
    Args:
        form_data (dict): Form data from request
        
    Returns:
        dict: Validated data
        
    Raises:
        ValidationError: If validation fails
    """
    validated = {}
    
    # Personal Information
    validated['name'] = form_data.get('name', '').strip()
    validate_required(validated['name'], "Name")
    
    if len(validated['name']) < 2:
        raise ValidationError("Name must be at least 2 characters")
    
    validated['phone'] = form_data.get('phone', '').strip()
    validate_phone(validated['phone'])
    
    validated['email'] = form_data.get('email', '').strip()
    if validated['email']:
        validate_email(validated['email'])
    
    validated['pan_card'] = form_data.get('pan_card', '').strip()
    if validated['pan_card']:
        validate_pan(validated['pan_card'])
    
    # Financial Information
    validated['monthly_income'] = validate_income(form_data.get('monthly_income', 0))
    validated['monthly_expenses'] = validate_expenses(
        form_data.get('monthly_expenses', 0),
        validated['monthly_income']
    )
    
    validated['income_std_dev'] = validate_amount(
        form_data.get('income_std_dev', 0),
        "Income variation",
        min_value=0,
        max_value=validated['monthly_income']
    )
    
    # Behavioral Metrics
    validated['upi_transactions'] = validate_integer(
        form_data.get('upi_transactions', 0),
        "UPI transactions",
        min_value=0,
        max_value=1000
    )
    
    validated['bill_payment_streak'] = validate_integer(
        form_data.get('bill_payment_streak', 0),
        "Bill payment streak",
        min_value=0,
        max_value=120
    )
    
    validated['digital_months'] = validate_integer(
        form_data.get('digital_months', 0),
        "Digital activity months",
        min_value=0,
        max_value=120
    )
    
    validated['savings_amount'] = validate_amount(
        form_data.get('savings_amount', 0),
        "Savings amount",
        min_value=0
    )
    
    # Business Information (Optional)
    validated['business_revenue'] = validate_amount(
        form_data.get('business_revenue', 0),
        "Business revenue",
        min_value=0
    )
    
    validated['business_expenses'] = validate_amount(
        form_data.get('business_expenses', 0),
        "Business expenses",
        min_value=0
    )
    
    return validated


def validate_file_upload(file):
    """
    Validate uploaded file.
    
    Args:
        file: FileStorage object from request
        
    Returns:
        bool: True if valid
        
    Raises:
        ValidationError: If file is invalid
    """
    if not file or not file.filename:
        raise ValidationError("No file selected")
    
    # Check file extension
    allowed_extensions = {'pdf', 'jpg', 'jpeg', 'png'}
    file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    
    if file_ext not in allowed_extensions:
        raise ValidationError(f"File type not allowed. Use: {', '.join(allowed_extensions)}")
    
    # Check file size (10MB limit)
    file.seek(0, 2)  # Seek to end
    file_size = file.tell()
    file.seek(0)  # Reset to start
    
    max_size = 10 * 1024 * 1024  # 10MB
    if file_size > max_size:
        raise ValidationError(f"File too large. Maximum size: {max_size // (1024*1024)}MB")
    
    if file_size == 0:
        raise ValidationError("File is empty")
    
    return True


def sanitize_filename(filename):
    """
    Sanitize filename to prevent directory traversal attacks.
    
    Args:
        filename (str): Original filename
        
    Returns:
        str: Sanitized filename
    """
    # Remove any path components
    filename = os.path.basename(filename)
    
    # Remove any non-alphanumeric characters except dots, dashes, underscores
    filename = re.sub(r'[^\w\s\-\.]', '', filename)
    
    # Replace spaces with underscores
    filename = filename.replace(' ', '_')
    
    # Limit length
    name, ext = os.path.splitext(filename)
    if len(name) > 100:
        name = name[:100]
    
    return f"{name}{ext}"


def validate_password_strength(password):
    """
    Validate password strength.
    
    Args:
        password (str): Password to validate
        
    Returns:
        bool: True if valid
        
    Raises:
        ValidationError: If password is weak
    """
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters long")
    
    if not re.search(r'[A-Z]', password):
        raise ValidationError("Password must contain at least one uppercase letter")
    
    if not re.search(r'[a-z]', password):
        raise ValidationError("Password must contain at least one lowercase letter")
    
    if not re.search(r'\d', password):
        raise ValidationError("Password must contain at least one number")
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        raise ValidationError("Password must contain at least one special character")
    
    # Check for common weak passwords
    weak_passwords = ['password123', 'admin123', 'pass123', '12345678']
    if password.lower() in weak_passwords:
        raise ValidationError("Password is too common. Please choose a stronger password")
    
    return True
