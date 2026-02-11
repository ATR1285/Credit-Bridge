"""
Configuration module for CreditBridge application.
Manages environment-specific settings and security configurations.
"""

import os
from datetime import timedelta

class Config:
    """Base configuration class with common settings."""
    
    # Security
    SECRET_KEY = os.getenv('SECRET_KEY', os.urandom(24).hex())
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///creditbridge.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True
    }
    
    # File Upload
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_UPLOAD_SIZE', 10 * 1024 * 1024))  # 10MB
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
    REPORTS_FOLDER = os.getenv('REPORTS_FOLDER', 'reports')
    ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}
    
    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(hours=int(os.getenv('SESSION_TIMEOUT_HOURS', 8)))
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # CSRF Protection
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # No timeout for CSRF tokens
    
    # Rate Limiting
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URL = os.getenv('REDIS_URL', 'memory://')
    
    # Google OAuth
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
    
    # Gemini AI
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    
    # Email Configuration
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@creditbridge.com')
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'logs/creditbridge.log')
    LOG_MAX_BYTES = int(os.getenv('LOG_MAX_BYTES', 10485760))  # 10MB
    LOG_BACKUP_COUNT = int(os.getenv('LOG_BACKUP_COUNT', 5))
    
    # File Cleanup
    FILE_RETENTION_DAYS = int(os.getenv('FILE_RETENTION_DAYS', 90))
    CLEANUP_SCHEDULE_HOURS = int(os.getenv('CLEANUP_SCHEDULE_HOURS', 24))
    
    # ML Model
    MODEL_PATH = os.getenv('MODEL_PATH', 'models/xgboost_model_v2.pkl')
    SCALER_PATH = os.getenv('SCALER_PATH', 'models/scaler_v2.pkl')
    
    # Application
    APP_NAME = 'CreditBridge'
    APP_VERSION = '3.0.1'


class DevelopmentConfig(Config):
    """Development environment configuration."""
    DEBUG = True
    TESTING = False
    
    # Less restrictive rate limiting for development
    RATELIMIT_ENABLED = False
    
    # Detailed logging
    LOG_LEVEL = 'DEBUG'


class ProductionConfig(Config):
    """Production environment configuration."""
    DEBUG = False
    TESTING = False
    
    # Enforce secure cookies
    SESSION_COOKIE_SECURE = True
    
    # Stricter rate limiting
    RATELIMIT_ENABLED = True
    
    # Production logging
    LOG_LEVEL = 'WARNING'


class TestingConfig(Config):
    """Testing environment configuration."""
    TESTING = True
    DEBUG = True
    
    # Use in-memory database for tests
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False
    
    # Disable rate limiting
    RATELIMIT_ENABLED = False


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(env=None):
    """
    Get configuration based on environment.
    
    Args:
        env (str): Environment name (development, production, testing)
        
    Returns:
        Config: Configuration object
    """
    if env is None:
        env = os.getenv('FLASK_ENV', 'development')
    
    return config.get(env, config['default'])
