"""
Timezone Utilities for CreditBridge

All database timestamps are stored in UTC.
This module provides helpers for timezone-aware analytics.

Usage:
    from timezone_utils import utc_now, to_user_tz, get_today_range
"""
from datetime import datetime, timedelta, timezone
from typing import Tuple, Optional
import pytz

# Default timezone for Indian Standard Time (most users)
DEFAULT_USER_TZ = pytz.timezone('Asia/Kolkata')

# UTC timezone
UTC = pytz.UTC


def utc_now() -> datetime:
    """Get current UTC time (timezone-aware)."""
    return datetime.now(UTC)


def to_utc(dt: datetime, source_tz: str = 'Asia/Kolkata') -> datetime:
    """
    Convert a naive or localized datetime to UTC.
    
    Args:
        dt: Datetime to convert
        source_tz: Source timezone name (IANA format)
        
    Returns:
        UTC datetime (timezone-aware)
    """
    tz = pytz.timezone(source_tz)
    
    if dt.tzinfo is None:
        # Naive datetime - assume it's in source_tz
        dt = tz.localize(dt)
    
    return dt.astimezone(UTC)


def to_user_tz(dt: datetime, user_tz: str = 'Asia/Kolkata') -> datetime:
    """
    Convert UTC datetime to user's local timezone.
    
    Args:
        dt: UTC datetime
        user_tz: Target timezone name
        
    Returns:
        Localized datetime
    """
    tz = pytz.timezone(user_tz)
    
    if dt.tzinfo is None:
        # Naive datetime - assume UTC
        dt = UTC.localize(dt)
    
    return dt.astimezone(tz)


def get_today_range_utc(user_tz: str = 'Asia/Kolkata') -> Tuple[datetime, datetime]:
    """
    Get UTC datetime range for "today" in user's timezone.
    
    This is critical for charts - we need to query the DB in UTC,
    but "today" is relative to the user's timezone.
    
    Args:
        user_tz: User's timezone
        
    Returns:
        (start_utc, end_utc) - UTC datetimes for start and end of user's "today"
    """
    tz = pytz.timezone(user_tz)
    
    # Get current time in user's timezone
    now_local = datetime.now(tz)
    
    # Start of today in user's timezone
    start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # End of today in user's timezone
    end_local = start_local + timedelta(days=1)
    
    # Convert to UTC for database queries
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def get_date_range_utc(
    start_date: datetime, 
    end_date: datetime, 
    user_tz: str = 'Asia/Kolkata'
) -> Tuple[datetime, datetime]:
    """
    Get UTC range for a date range in user's timezone.
    
    Args:
        start_date: Start date (naive, assumed in user_tz)
        end_date: End date (naive, assumed in user_tz)
        user_tz: User's timezone
        
    Returns:
        (start_utc, end_utc)
    """
    tz = pytz.timezone(user_tz)
    
    start = tz.localize(start_date.replace(hour=0, minute=0, second=0, microsecond=0))
    end = tz.localize(end_date.replace(hour=23, minute=59, second=59, microsecond=999999))
    
    return start.astimezone(UTC), end.astimezone(UTC)


def get_past_days_range_utc(
    days: int, 
    user_tz: str = 'Asia/Kolkata'
) -> Tuple[datetime, datetime]:
    """
    Get UTC range for the past N days in user's timezone.
    
    Args:
        days: Number of past days
        user_tz: User's timezone
        
    Returns:
        (start_utc, end_utc)
    """
    tz = pytz.timezone(user_tz)
    
    now_local = datetime.now(tz)
    end_local = now_local.replace(hour=23, minute=59, second=59, microsecond=999999)
    start_local = (now_local - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def format_for_display(dt: datetime, user_tz: str = 'Asia/Kolkata', fmt: str = '%d %b %Y %I:%M %p') -> str:
    """
    Format UTC datetime for display in user's timezone.
    
    Args:
        dt: UTC datetime
        user_tz: User's timezone
        fmt: strftime format
        
    Returns:
        Formatted string in user's timezone
    """
    local_dt = to_user_tz(dt, user_tz)
    return local_dt.strftime(fmt)


# ============================================================================
# CHART QUERY HELPERS
# ============================================================================

def get_hourly_buckets_utc(user_tz: str = 'Asia/Kolkata') -> list:
    """
    Get UTC timestamps for each hour of today in user's timezone.
    Useful for hourly chart data.
    """
    start_utc, _ = get_today_range_utc(user_tz)
    
    buckets = []
    for hour in range(24):
        bucket_start = start_utc + timedelta(hours=hour)
        bucket_end = bucket_start + timedelta(hours=1)
        buckets.append({
            'hour': hour,
            'start_utc': bucket_start,
            'end_utc': bucket_end
        })
    
    return buckets


def is_same_day_utc(dt1: datetime, dt2: datetime, user_tz: str = 'Asia/Kolkata') -> bool:
    """
    Check if two UTC datetimes fall on the same calendar day in user's timezone.
    """
    local1 = to_user_tz(dt1, user_tz)
    local2 = to_user_tz(dt2, user_tz)
    
    return local1.date() == local2.date()
