"""
Dashboard Service Layer

Provides unified data scope for all dashboard widgets.
Ensures branch isolation and consistent date ranges.

Usage:
    from dashboard_service import DashboardService, DatePreset
    
    # Create context from session
    ctx = DashboardService.from_session(session, DatePreset.LAST_7_DAYS)
    
    # All widgets use same context
    summary = ctx.get_summary()
    risk_dist = ctx.get_risk_distribution()
    trends = ctx.get_daily_trends()
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple
from functools import lru_cache
import json

from flask import session
from sqlalchemy import func, and_, or_, case

# Import after app context available
# from app import db, CreditAssessment, Employee, Branch


class DatePreset(Enum):
    """Predefined date ranges for dashboards."""
    TODAY = "today"
    LAST_7_DAYS = "7d"
    LAST_30_DAYS = "30d"
    THIS_MONTH = "month"
    THIS_QUARTER = "quarter"
    CUSTOM = "custom"


@dataclass
class DashboardContext:
    """
    Unified context for all dashboard queries.
    
    This ensures ALL widgets use the SAME:
    - branch_id (or all branches for head_of_bank)
    - date_from and date_to
    - timezone settings
    
    Attributes:
        employee_id: Current logged-in employee
        role: Employee role for access control
        branch_id: Branch filter (None = all branches)
        date_from: Start of date range (UTC)
        date_to: End of date range (UTC)  
        preset: Which date preset is active
        user_tz: User's timezone for display
    """
    employee_id: int
    role: str
    branch_id: Optional[int]  # None = global access (head_of_bank)
    date_from: datetime
    date_to: datetime
    preset: DatePreset = DatePreset.LAST_7_DAYS
    user_tz: str = 'Asia/Kolkata'
    
    def is_global_view(self) -> bool:
        """Check if user has access to all branches."""
        return self.branch_id is None
    
    def get_date_range_display(self) -> str:
        """Get human-readable date range."""
        if self.preset == DatePreset.TODAY:
            return "Today"
        elif self.preset == DatePreset.LAST_7_DAYS:
            return "Last 7 Days"
        elif self.preset == DatePreset.LAST_30_DAYS:
            return "Last 30 Days"
        elif self.preset == DatePreset.THIS_MONTH:
            return "This Month"
        else:
            return f"{self.date_from.strftime('%d %b')} - {self.date_to.strftime('%d %b %Y')}"


class DashboardService:
    """
    Service layer for unified dashboard data.
    
    All widgets call methods on this service with the same context,
    ensuring data consistency across the entire dashboard.
    """
    
    def __init__(self, ctx: DashboardContext, db, models: dict):
        """
        Initialize dashboard service.
        
        Args:
            ctx: Dashboard context with scope
            db: SQLAlchemy database instance
            models: Dict with model classes {CreditAssessment, Employee, Branch}
        """
        self.ctx = ctx
        self.db = db
        self.CreditAssessment = models['CreditAssessment']
        self.Employee = models['Employee']
        self.Branch = models.get('Branch')
        
        # Cache for expensive computations
        self._cache: Dict[str, Any] = {}
    
    @classmethod
    def from_session(
        cls, 
        session_data: dict, 
        preset: DatePreset = DatePreset.LAST_7_DAYS,
        custom_from: datetime = None,
        custom_to: datetime = None,
        user_tz: str = 'Asia/Kolkata'
    ):
        """
        Create dashboard service from Flask session.
        
        Args:
            session_data: Flask session dict
            preset: Date preset to use
            custom_from: Custom start date (if preset=CUSTOM)
            custom_to: Custom end date (if preset=CUSTOM)
            user_tz: User's timezone
            
        Returns:
            DashboardService instance
        """
        from app import db, CreditAssessment, Employee, Branch
        from timezone_utils import get_today_range_utc, get_past_days_range_utc
        
        employee_id = session_data.get('employee_id')
        employee = Employee.query.get(employee_id)
        
        if not employee:
            raise ValueError("Employee not found in session")
        
        # Determine branch access
        # head_of_bank sees all branches (branch_id = None)
        # Others see only their branch
        if employee.role == 'head_of_bank':
            branch_id = None
        else:
            branch_id = employee.branch_id
        
        # Calculate date range
        date_from, date_to = cls._calculate_date_range(preset, custom_from, custom_to, user_tz)
        
        ctx = DashboardContext(
            employee_id=employee_id,
            role=employee.role,
            branch_id=branch_id,
            date_from=date_from,
            date_to=date_to,
            preset=preset,
            user_tz=user_tz
        )
        
        models = {
            'CreditAssessment': CreditAssessment,
            'Employee': Employee,
            'Branch': Branch
        }
        
        return cls(ctx, db, models)
    
    @staticmethod
    def _calculate_date_range(
        preset: DatePreset,
        custom_from: datetime,
        custom_to: datetime,
        user_tz: str
    ) -> Tuple[datetime, datetime]:
        """Calculate UTC date range from preset."""
        from timezone_utils import get_today_range_utc, get_past_days_range_utc, to_utc
        import pytz
        
        if preset == DatePreset.TODAY:
            return get_today_range_utc(user_tz)
        
        elif preset == DatePreset.LAST_7_DAYS:
            return get_past_days_range_utc(7, user_tz)
        
        elif preset == DatePreset.LAST_30_DAYS:
            return get_past_days_range_utc(30, user_tz)
        
        elif preset == DatePreset.THIS_MONTH:
            tz = pytz.timezone(user_tz)
            now = datetime.now(tz)
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            return start.astimezone(pytz.UTC), end.astimezone(pytz.UTC)
        
        elif preset == DatePreset.CUSTOM and custom_from and custom_to:
            return to_utc(custom_from, user_tz), to_utc(custom_to, user_tz)
        
        else:
            # Default: last 7 days
            return get_past_days_range_utc(7, user_tz)
    
    # =========================================================================
    # BASE QUERY WITH FILTERS
    # =========================================================================
    
    def _base_query(self):
        """
        Create base query with branch and date filters applied.
        
        This is the core method that ensures ALL widgets use the same scope.
        """
        query = self.CreditAssessment.query.filter(
            self.CreditAssessment.assessment_date >= self.ctx.date_from,
            self.CreditAssessment.assessment_date < self.ctx.date_to
        )
        
        # Branch filter (skip for head_of_bank)
        if self.ctx.branch_id is not None:
            query = query.filter(self.CreditAssessment.branch_id == self.ctx.branch_id)
        
        return query
    
    # =========================================================================
    # WIDGET DATA METHODS
    # =========================================================================
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics for dashboard cards.
        
        Returns:
            {
                'total': int,
                'approved': int,
                'rejected': int,
                'pending': int,
                'approval_rate': float
            }
        """
        cache_key = 'summary'
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        base = self._base_query()
        
        total = base.count()
        approved = base.filter(self.CreditAssessment.status == 'approved').count()
        rejected = base.filter(self.CreditAssessment.status == 'rejected').count()
        pending = base.filter(
            self.CreditAssessment.status.in_([
                'draft', 'pending_review', 'under_review', 
                'reviewed', 'pending_approval', 'escalated'
            ])
        ).count()
        
        approval_rate = (approved / total * 100) if total > 0 else 0
        
        result = {
            'total': total,
            'approved': approved,
            'rejected': rejected,
            'pending': pending,
            'approval_rate': round(approval_rate, 1)
        }
        
        self._cache[cache_key] = result
        return result
    
    def get_risk_distribution(self) -> Dict[str, int]:
        """
        Get risk category distribution for donut chart.
        
        Returns:
            {'Low': 45, 'Medium': 30, 'High': 25}
        """
        cache_key = 'risk_dist'
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        results = self.db.session.query(
            self.CreditAssessment.risk_category,
            func.count(self.CreditAssessment.id)
        ).filter(
            self.CreditAssessment.assessment_date >= self.ctx.date_from,
            self.CreditAssessment.assessment_date < self.ctx.date_to
        )
        
        if self.ctx.branch_id is not None:
            results = results.filter(self.CreditAssessment.branch_id == self.ctx.branch_id)
        
        results = results.group_by(self.CreditAssessment.risk_category).all()
        
        distribution = {row[0]: row[1] for row in results if row[0]}
        
        self._cache[cache_key] = distribution
        return distribution
    
    def get_daily_trends(self) -> List[Dict[str, Any]]:
        """
        Get daily assessment counts for trend chart.
        
        Returns:
            [{'date': '2026-01-15', 'count': 12, 'approved': 8}, ...]
        """
        cache_key = 'daily_trends'
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Group by date
        date_col = func.date(self.CreditAssessment.assessment_date)
        
        query = self.db.session.query(
            date_col.label('date'),
            func.count(self.CreditAssessment.id).label('total'),
            func.sum(
                case((self.CreditAssessment.status == 'approved', 1), else_=0)
            ).label('approved')
        ).filter(
            self.CreditAssessment.assessment_date >= self.ctx.date_from,
            self.CreditAssessment.assessment_date < self.ctx.date_to
        )
        
        if self.ctx.branch_id is not None:
            query = query.filter(self.CreditAssessment.branch_id == self.ctx.branch_id)
        
        results = query.group_by(date_col).order_by(date_col).all()
        
        trends = [
            {
                'date': str(row.date),
                'total': row.total,
                'approved': row.approved or 0
            }
            for row in results
        ]
        
        self._cache[cache_key] = trends
        return trends
    
    def get_score_distribution(self) -> List[Dict[str, Any]]:
        """
        Get credit score distribution for histogram.
        
        Returns:
            [{'range': '300-400', 'count': 5}, ...]
        """
        cache_key = 'score_dist'
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Define score buckets
        buckets = [
            (300, 400), (400, 500), (500, 600), 
            (600, 700), (700, 800), (800, 900)
        ]
        
        distribution = []
        
        for low, high in buckets:
            query = self._base_query().filter(
                self.CreditAssessment.credit_score >= low,
                self.CreditAssessment.credit_score < high
            )
            count = query.count()
            distribution.append({
                'range': f'{low}-{high}',
                'count': count
            })
        
        self._cache[cache_key] = distribution
        return distribution
    
    def get_recent_assessments(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent assessments for table widget.
        
        Args:
            limit: Max number of records
            
        Returns:
            List of assessment dicts
        """
        assessments = self._base_query().order_by(
            self.CreditAssessment.assessment_date.desc()
        ).limit(limit).all()
        
        return [
            {
                'id': a.id,
                'credit_score': a.credit_score,
                'risk_category': a.risk_category,
                'status': a.status,
                'date': a.assessment_date.strftime('%Y-%m-%d %H:%M')
            }
            for a in assessments
        ]
    
    def get_employee_performance(self) -> List[Dict[str, Any]]:
        """
        Get employee performance stats.
        
        Returns:
            [{'name': 'John', 'count': 15, 'approved': 12}, ...]
        """
        cache_key = 'emp_perf'
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        query = self.db.session.query(
            self.Employee.full_name,
            func.count(self.CreditAssessment.id).label('total'),
            func.sum(
                case((self.CreditAssessment.status == 'approved', 1), else_=0)
            ).label('approved')
        ).join(
            self.CreditAssessment,
            self.CreditAssessment.created_by == self.Employee.id
        ).filter(
            self.CreditAssessment.assessment_date >= self.ctx.date_from,
            self.CreditAssessment.assessment_date < self.ctx.date_to
        )
        
        if self.ctx.branch_id is not None:
            query = query.filter(self.Employee.branch_id == self.ctx.branch_id)
        
        results = query.group_by(self.Employee.id, self.Employee.full_name).all()
        
        performance = [
            {
                'name': row.full_name,
                'total': row.total,
                'approved': row.approved or 0
            }
            for row in results
        ]
        
        self._cache[cache_key] = performance
        return performance
    
    def get_all_widgets(self) -> Dict[str, Any]:
        """
        Get ALL widget data in a single call.
        
        This ensures atomic snapshot of dashboard data.
        
        Returns:
            {
                'context': {...},
                'summary': {...},
                'risk_distribution': {...},
                'daily_trends': [...],
                'score_distribution': [...],
                'recent': [...],
                'employee_performance': [...]
            }
        """
        return {
            'context': {
                'branch_id': self.ctx.branch_id,
                'date_from': self.ctx.date_from.isoformat(),
                'date_to': self.ctx.date_to.isoformat(),
                'preset': self.ctx.preset.value,
                'date_range_display': self.ctx.get_date_range_display(),
                'is_global': self.ctx.is_global_view()
            },
            'summary': self.get_summary(),
            'risk_distribution': self.get_risk_distribution(),
            'daily_trends': self.get_daily_trends(),
            'score_distribution': self.get_score_distribution(),
            'recent': self.get_recent_assessments(),
            'employee_performance': self.get_employee_performance()
        }
