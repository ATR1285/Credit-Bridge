import os
import json
import uuid
import secrets
import random
import tempfile
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash, send_file, abort
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from authlib.integrations.flask_client import OAuth
import requests
from dotenv import load_dotenv

# Import our custom modules
from ml_model import CreditMLModel, initialize_model
from document_analyzer import DocumentAnalyzer
from pdf_generator import CreditReportGenerator

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(24))
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///creditbridge.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 10485760))  # 10MB
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'uploads')
app.config['REPORTS_FOLDER'] = os.getenv('REPORTS_FOLDER', 'reports')

# Initialize extensions
db = SQLAlchemy(app)
CORS(app)
oauth = OAuth(app)

# Google OAuth configuration
# Only register if credentials are available
if os.getenv('GOOGLE_CLIENT_ID') and os.getenv('GOOGLE_CLIENT_SECRET'):
    google = oauth.register(
        name='google',
        client_id=os.getenv('GOOGLE_CLIENT_ID'),
        client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile'
        }
    )
else:
    google = None

# Initialize global components
ml_model = None
document_analyzer = None
pdf_generator = None

# Database Models

# ============================================================================
# BRANCH MODEL - Multi-Branch Support
# ============================================================================

class Branch(db.Model):
    """Bank branch information for multi-branch support"""
    __tablename__ = 'branches'
    
    id = db.Column(db.Integer, primary_key=True)
    branch_code = db.Column(db.String(20), unique=True, nullable=False)  # e.g., 'BR001'
    branch_name = db.Column(db.String(100), nullable=False)  # e.g., 'Downtown Branch'
    
    # Location Info
    address = db.Column(db.Text)
    city = db.Column(db.String(50))
    state = db.Column(db.String(50))
    pincode = db.Column(db.String(10))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    
    # Management
    manager_id = db.Column(db.Integer)  # Branch Manager employee ID (can't use FK due to ordering)
    status = db.Column(db.String(20), default='active')  # active/inactive/closed
    
    # Targets & Metrics
    monthly_target = db.Column(db.Integer, default=100)  # Assessment target
    daily_target = db.Column(db.Integer, default=10)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def get_employees(self):
        """Get all employees in this branch"""
        return Employee.query.filter_by(branch_id=self.id, status='ACTIVE').all()
    
    def get_assessments_count(self, days=30):
        """Get assessment count for this branch in last N days"""
        from sqlalchemy import and_
        cutoff = datetime.utcnow() - timedelta(days=days)
        return CreditAssessment.query.filter(
            and_(
                CreditAssessment.branch_id == self.id,
                CreditAssessment.assessment_date >= cutoff
            )
        ).count()


class Customer(db.Model):
    """Public portal users (Google OAuth)"""
    __tablename__ = 'customers'
    
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(128), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    profile_picture = db.Column(db.String(512))
    phone = db.Column(db.String(20))
    aadhaar_last_4 = db.Column(db.String(4))
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    users = db.relationship('User', backref='customer', lazy=True)
    document_uploads = db.relationship('DocumentUpload', backref='customer', lazy=True)
    score_history = db.relationship('ScoreHistory', backref='customer', lazy=True)
    improvement_plans = db.relationship('ImprovementPlan', backref='customer', lazy=True)


class Employee(db.Model):
    """Bank staff accounts with 5-role hierarchy and multi-branch support"""
    __tablename__ = 'employees'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(60), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120))
    employee_code = db.Column(db.String(20), unique=True)  # e.g., 'EMP001'
    
    # Role: head_of_bank, branch_manager, credit_manager, loan_officer, credit_analyst
    role = db.Column(db.String(80), nullable=False)
    permissions = db.Column(db.Text, nullable=False)  # JSON array of permissions
    
    # Multi-Branch Support - NULL for head_of_bank (sees all branches)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    
    # Team Structure
    team_id = db.Column(db.String(50))  # e.g., "sales_team_1", "credit_team_a"
    manager_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    department = db.Column(db.String(50), default='retail_banking')  # retail_banking, commercial_banking, etc.
    
    # Status & Activity (NEW)
    status = db.Column(db.String(20), default='ACTIVE')  # ACTIVE, INACTIVE, ON_LEAVE
    last_login = db.Column(db.DateTime)
    daily_assessment_count = db.Column(db.Integer, default=0)  # Resets daily
    avg_processing_time_minutes = db.Column(db.Float, default=0.0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Self-referential relationship for manager hierarchy
    subordinates = db.relationship('Employee', backref=db.backref('manager', remote_side=[id]), lazy='dynamic')
    
    # Relationships - assessments they processed/created
    created_assessments = db.relationship('CreditAssessment', foreign_keys='CreditAssessment.created_by', backref='creator', lazy='dynamic')
    assigned_assessments = db.relationship('CreditAssessment', foreign_keys='CreditAssessment.assigned_to', backref='assignee', lazy='dynamic')
    approved_assessments = db.relationship('CreditAssessment', foreign_keys='CreditAssessment.approved_by', backref='approver', lazy='dynamic')
    reviewed_assessments = db.relationship('CreditAssessment', foreign_keys='CreditAssessment.reviewed_by', backref='reviewer', lazy='dynamic')
    
    # Audit logs
    audit_logs = db.relationship('AuditLog', backref='employee', lazy='dynamic')
    notifications = db.relationship('Notification', backref='employee', lazy='dynamic')
    
    def has_permission(self, permission):
        """Check if employee has a specific permission"""
        perms = json.loads(self.permissions) if self.permissions else []
        # SUPER_ADMIN bypasses all permission checks
        if 'SUPER_ADMIN' in perms:
            return True
        return 'ALL' in perms or permission in perms
    
    def is_super_admin(self):
        """Check if employee is a super admin (head_of_bank)"""
        perms = json.loads(self.permissions) if self.permissions else []
        return 'SUPER_ADMIN' in perms
    
    def get_branch(self):
        """Get the employee's branch object"""
        if not self.branch_id:
            return None
        return Branch.query.get(self.branch_id)
    
    def get_team_members(self):
        """Get all employees in the same team"""
        if not self.team_id:
            return []
        return Employee.query.filter_by(team_id=self.team_id, status='ACTIVE').all()
    
    def get_branch_employees(self):
        """Get all employees in the same branch"""
        if not self.branch_id:
            return []
        return Employee.query.filter_by(branch_id=self.branch_id, status='ACTIVE').all()
    
    def get_subordinates_recursive(self):
        """Get all subordinates recursively (for managers)"""
        result = []
        for sub in self.subordinates:
            result.append(sub)
            result.extend(sub.get_subordinates_recursive())
        return result


# ============================================================================
# NEW MODELS FOR ROLE-BASED WORKFLOW
# ============================================================================

class AuditLog(db.Model):
    """Comprehensive audit trail for all system actions"""
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)  # Nullable for system actions
    
    # Action details
    action = db.Column(db.String(50), nullable=False)  # CREATE, UPDATE, DELETE, VIEW, OVERRIDE, APPROVE, REJECT, REASSIGN, LOGIN, LOGOUT
    entity_type = db.Column(db.String(50), nullable=False)  # assessment, employee, customer, document, settings
    entity_id = db.Column(db.Integer)  # ID of the affected entity
    
    # Change tracking
    before_value_json = db.Column(db.Text)  # State BEFORE change
    after_value_json = db.Column(db.Text)   # State AFTER change
    details_json = db.Column(db.Text)       # Additional context
    
    # Request metadata
    ip_address = db.Column(db.String(45))   # IPv6 compatible
    user_agent = db.Column(db.String(512))
    
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    @staticmethod
    def log(employee_id, action, entity_type, entity_id=None, before=None, after=None, details=None, ip=None, user_agent=None):
        """Static method to create audit log entry"""
        log_entry = AuditLog(
            employee_id=employee_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_value_json=json.dumps(before) if before else None,
            after_value_json=json.dumps(after) if after else None,
            details_json=json.dumps(details) if details else None,
            ip_address=ip,
            user_agent=user_agent
        )
        db.session.add(log_entry)
        return log_entry


class AssignmentHistory(db.Model):
    """Track assessment assignment changes"""
    __tablename__ = 'assignment_history'
    
    id = db.Column(db.Integer, primary_key=True)
    assessment_id = db.Column(db.Integer, db.ForeignKey('credit_assessments.id'), nullable=False)
    
    # Assignment details
    assigned_from = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)  # Nullable for initial creation
    assigned_to = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    assignment_type = db.Column(db.String(20), nullable=False)  # AUTO, MANUAL, REASSIGN
    reason = db.Column(db.Text)  # Required for MANUAL and REASSIGN
    
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    from_employee = db.relationship('Employee', foreign_keys=[assigned_from])
    to_employee = db.relationship('Employee', foreign_keys=[assigned_to])


class Notification(db.Model):
    """In-app notifications for employees"""
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    assessment_id = db.Column(db.Integer, db.ForeignKey('credit_assessments.id'), nullable=True)
    
    notification_type = db.Column(db.String(30), nullable=False)  # ASSIGNED, REVIEWED, APPROVED, REJECTED, ESCALATED, OVERRIDE, RESUBMITTED
    message = db.Column(db.Text, nullable=False)
    
    read_status = db.Column(db.Boolean, default=False)
    priority = db.Column(db.String(10), default='MEDIUM')  # LOW, MEDIUM, HIGH, URGENT
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    read_at = db.Column(db.DateTime, nullable=True)
    
    # Relationship to assessment
    assessment = db.relationship('CreditAssessment', backref='notifications')
    
    @staticmethod
    def create(employee_id, notification_type, message, assessment_id=None, priority='MEDIUM'):
        """Static method to create notification"""
        notification = Notification(
            employee_id=employee_id,
            assessment_id=assessment_id,
            notification_type=notification_type,
            message=message,
            priority=priority
        )
        db.session.add(notification)
        return notification
    
    def mark_as_read(self):
        """Mark notification as read"""
        self.read_status = True
        self.read_at = datetime.utcnow()


class User(db.Model):
    """Applicants (renamed internally as Applicant model)"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120))
    pan_card = db.Column(db.String(10))
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    financial_profile = db.relationship('FinancialProfile', backref='user', uselist=False, lazy=True)
    assessments = db.relationship('CreditAssessment', backref='user', lazy=True)
    documents = db.relationship('DocumentUpload', backref='user', lazy=True)

class FinancialProfile(db.Model):
    """Financial profile data"""
    __tablename__ = 'financial_profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    monthly_income = db.Column(db.Float, nullable=False)
    monthly_expenses = db.Column(db.Float, nullable=False)
    income_std_dev = db.Column(db.Float, default=0)
    upi_transaction_count = db.Column(db.Integer, default=0)
    bill_payment_streak = db.Column(db.Integer, default=0)
    digital_activity_months = db.Column(db.Integer, default=0)
    savings_amount = db.Column(db.Float, default=0)
    business_revenue = db.Column(db.Float, default=0)
    business_expenses = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    assessments = db.relationship('CreditAssessment', backref='profile', lazy=True)

class CreditAssessment(db.Model):
    """Credit assessment results with complete workflow support"""
    __tablename__ = 'credit_assessments'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    profile_id = db.Column(db.Integer, db.ForeignKey('financial_profiles.id'), nullable=False)
    
    # Core Assessment Data
    credit_score = db.Column(db.Integer, nullable=False)
    risk_category = db.Column(db.String(20), nullable=False)  # Low, Medium, High
    repayment_probability = db.Column(db.Float, nullable=False)
    features_json = db.Column(db.Text, nullable=False)
    document_bonus = db.Column(db.Integer, default=0)
    model_used = db.Column(db.String(20), default='xgboost')
    
    # Workflow Fields (NEW)
    created_by = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)  # NULL = public portal
    assigned_to = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)  # Credit Analyst
    reviewed_by = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)  # Who completed review
    approved_by = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)  # Who approved/rejected
    
    # Status Workflow
    # Values: draft, pending_review, under_review, reviewed, pending_approval, approved, rejected, escalated
    status = db.Column(db.String(30), default='draft')
    previous_status = db.Column(db.String(30), nullable=True)  # For rollback capability
    
    # Priority & SLA
    priority = db.Column(db.String(20), default='normal')  # normal, high, urgent
    sla_deadline = db.Column(db.DateTime, nullable=True)  # Calculated based on priority
    
    # Notes & Comments
    override_notes = db.Column(db.Text, nullable=True)  # Notes when overriding decisions
    review_notes = db.Column(db.Text, nullable=True)  # Analyst review notes
    rejection_reason = db.Column(db.Text, nullable=True)  # Why rejected
    escalation_reason = db.Column(db.Text, nullable=True)  # Why escalated
    
    # Timestamps
    assessment_date = db.Column(db.DateTime, default=datetime.utcnow)  # Creation date
    submitted_at = db.Column(db.DateTime, nullable=True)  # When submitted for review
    reviewed_at = db.Column(db.DateTime, nullable=True)  # When review completed
    approved_at = db.Column(db.DateTime, nullable=True)  # When approved/rejected
    
    # Processing Metrics
    processing_time_minutes = db.Column(db.Integer, nullable=True)  # Time from creation to final decision
    
    # Legacy field for backward compatibility
    processed_by = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    
    # Relationship to AssignmentHistory
    assignment_history = db.relationship('AssignmentHistory', backref='assessment', lazy='dynamic')
    
    def is_editable_by(self, employee):
        """Check if this assessment can be edited by the given employee"""
        if employee.has_permission('ALL'):
            return True
        
        if employee.role == 'loan_officer':
            # Can only edit own drafts
            return self.created_by == employee.id and self.status == 'draft'
        
        elif employee.role == 'credit_analyst':
            # Can only edit if assigned to them and in review status
            return self.assigned_to == employee.id and self.status in ['pending_review', 'under_review']
        
        elif employee.role == 'credit_manager':
            # Can edit team assessments in certain statuses
            team_ids = [e.id for e in employee.get_team_members()]
            return (self.created_by in team_ids or self.assigned_to in team_ids) and \
                   self.status in ['reviewed', 'pending_approval', 'escalated']
        
        return False
    
    def can_be_viewed_by(self, employee):
        """Check if this assessment can be viewed by the given employee"""
        if employee.has_permission('ALL') or employee.has_permission('VIEW_ALL_ASSESSMENTS'):
            return True
        
        if employee.role == 'loan_officer':
            return self.created_by == employee.id
        
        elif employee.role == 'credit_analyst':
            return self.assigned_to == employee.id
        
        elif employee.role == 'credit_manager':
            team_ids = [e.id for e in employee.get_team_members()]
            return self.created_by in team_ids or self.assigned_to in team_ids
        
        return False
    
    def calculate_sla_deadline(self):
        """Calculate SLA deadline based on priority"""
        if self.priority == 'urgent':
            return datetime.utcnow() + timedelta(hours=4)
        elif self.priority == 'high':
            return datetime.utcnow() + timedelta(hours=24)
        else:  # normal
            return datetime.utcnow() + timedelta(hours=72)
    
    def to_audit_dict(self):
        """Convert to dictionary for audit logging"""
        return {
            'id': self.id,
            'status': self.status,
            'credit_score': self.credit_score,
            'risk_category': self.risk_category,
            'assigned_to': self.assigned_to,
            'approved_by': self.approved_by,
            'priority': self.priority
        }


class DocumentUpload(db.Model):
    """Document upload records"""
    __tablename__ = 'document_uploads'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    document_type = db.Column(db.String(50), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    file_size = db.Column(db.Integer)
    verified_status = db.Column(db.String(20), default='pending')
    ai_verification_score = db.Column(db.Float)
    analysis_json = db.Column(db.Text, default='{}')
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

class ScoreHistory(db.Model):
    """Score history tracking"""
    __tablename__ = 'score_history'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    assessment_id = db.Column(db.Integer, db.ForeignKey('credit_assessments.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    risk_category = db.Column(db.String(20), nullable=False)
    document_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ImprovementPlan(db.Model):
    """Improvement plan tracking"""
    __tablename__ = 'improvement_plans'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    assessment_id = db.Column(db.Integer, db.ForeignKey('credit_assessments.id'), nullable=False)
    current_score = db.Column(db.Integer, nullable=False)
    target_score = db.Column(db.Integer, nullable=False)
    suggestions_json = db.Column(db.Text, nullable=False)
    progress_percentage = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


# ============================================================================
# ROLE-BASED PERMISSIONS CONFIGURATION
# ============================================================================

ROLE_PERMISSIONS = {
    'head_of_bank': [
        'SUPER_ADMIN',  # Bypass all permission checks
        
        # View Everything
        'VIEW_ALL_BRANCHES',
        'VIEW_ALL_ASSESSMENTS',
        'VIEW_ALL_CUSTOMERS',
        'VIEW_ALL_EMPLOYEES',
        'VIEW_ALL_AUDIT_LOGS',
        'VIEW_SYSTEM_LOGS',
        
        # Edit Everything
        'EDIT_ANY_ASSESSMENT',
        'OVERRIDE_ANY_DECISION',
        'OVERRIDE_BRANCH_MANAGER',
        'DELETE_ANY_RECORD',
        
        # Manage Everything
        'MANAGE_BRANCHES',
        'CREATE_BRANCH',
        'EDIT_BRANCH',
        'CLOSE_BRANCH',
        'MANAGE_BRANCH_MANAGERS',
        'HIRE_FIRE_EMPLOYEES',
        'CONFIGURE_CREDIT_POLICIES',
        'MANAGE_SYSTEM_SETTINGS',
        'CONFIGURE_ML_MODEL',
        
        # Reports & Analytics
        'VIEW_EXECUTIVE_DASHBOARD',
        'VIEW_COMPARATIVE_ANALYTICS',
        'VIEW_FRAUD_REPORTS',
        'EXPORT_ALL_REPORTS',
        'VIEW_REVENUE_ANALYTICS',
        
        # Critical Actions
        'APPROVE_HIGH_VALUE_LOANS',  # >$100K
        'EMERGENCY_OVERRIDE',
        'PURGE_DATA',
        'ACCESS_DEVELOPER_TOOLS',
        
        # Legacy permissions for backward compatibility
        'ALL',
        # 'CREATE_ASSESSMENT',  # REMOVED - Only Loan Officers create assessments
        'VIEW_AUDIT_LOGS',
        'CONFIGURE_SETTINGS'
    ],
    'branch_manager': [
        'ALL',  # Full access within branch - bypass permission checks for branch data
        
        # View Branch-Level Data
        'VIEW_BRANCH_ASSESSMENTS',
        'VIEW_BRANCH_CUSTOMERS',
        'VIEW_BRANCH_EMPLOYEES',
        'VIEW_BRANCH_ANALYTICS',
        'VIEW_BRANCH_AUDIT_LOGS',
        
        # Edit Branch Data
        # 'CREATE_ASSESSMENT',  # REMOVED - Only Loan Officers create assessments
        'VIEW_ALL_ASSESSMENTS',
        'EDIT_ANY_ASSESSMENT',
        'EDIT_BRANCH_ASSESSMENTS',
        'DELETE_ASSESSMENT',
        'DELETE_DRAFT_ASSESSMENTS',
        'OVERRIDE_DECISION',
        'REASSIGN_ANY_ASSESSMENT',
        
        # Manage Branch Team
        'MANAGE_USERS',
        'MANAGE_BRANCH_EMPLOYEES',
        'ADD_EMPLOYEE',
        'EDIT_EMPLOYEE',
        'DEACTIVATE_EMPLOYEE',
        'ASSIGN_TEAMS',
        'SET_EMPLOYEE_TARGETS',
        
        # Approvals
        'APPROVE_HIGH_RISK',  # Score < 550
        'APPROVE_MEDIUM_VALUE_LOANS',  # $50K-$100K
        'APPROVE_POLICY_EXCEPTIONS',
        'FINAL_APPROVAL_AUTHORITY',
        
        # Reports
        'VIEW_AUDIT_LOGS',
        'EXPORT_ALL_REPORTS',
        'EXPORT_BRANCH_REPORTS',
        'VIEW_TEAM_PERFORMANCE',
        'VIEW_PORTFOLIO_RISK',
        'VIEW_ALL_CUSTOMERS',
        
        # Configuration
        'CONFIGURE_SETTINGS',
        'CONFIGURE_BRANCH_SETTINGS',
        'SET_BRANCH_TARGETS',
        'BULK_APPROVE'
    ],
    'credit_manager': [
        # View Team Data
        'VIEW_TEAM_ASSESSMENTS',
        'VIEW_TEAM_CUSTOMERS',
        'VIEW_TEAM_PERFORMANCE',
        'VIEW_PORTFOLIO_ANALYTICS',
        
        # Edit Team Data
        # 'CREATE_ASSESSMENT',  # REMOVED - Only Loan Officers create assessments
        'EDIT_TEAM_ASSESSMENTS',
        'ADD_REVIEW_NOTES',
        
        # Decision Making
        'APPROVE_ASSESSMENTS',
        'REJECT_ASSESSMENTS',
        'RECOMMEND_OVERRIDE',
        
        # Quality Control
        'VIEW_ESCALATIONS',
        'REVIEW_ANALYST_WORK',
        'REASSIGN_TEAM_ASSESSMENTS',
        'ESCALATE_TO_BRANCH_MANAGER',
        'FLAG_QUALITY_ISSUES',
        
        # Team Management
        'VIEW_ANALYST_WORKLOAD',
        'ASSIGN_ASSESSMENTS',
        'MENTOR_ANALYSTS',
        
        # Reports
        'EXPORT_TEAM_REPORTS',
        'VIEW_APPROVAL_TRENDS'
    ],
    'loan_officer': [
        # Create & View Own Data
        'CREATE_ASSESSMENT',
        'VIEW_OWN_ASSESSMENTS',
        'VIEW_OWN_CUSTOMERS',
        'VIEW_OWN_PERFORMANCE',
        
        # Edit Own Data
        'EDIT_OWN_DRAFT',  # Only if status='draft'
        'DELETE_OWN_DRAFT',
        'UPLOAD_DOCUMENTS',
        'UPDATE_CUSTOMER_INFO',
        
        # Workflow Actions
        'SUBMIT_FOR_REVIEW',
        'RESUBMIT_REJECTED',
        'REQUEST_REASSIGNMENT',
        'ADD_APPLICANT_NOTES',
        
        # Customer Interaction
        'VIEW_ASSESSMENT_STATUS',
        'DOWNLOAD_RESULT_PDF',
        'SEND_CUSTOMER_NOTIFICATION'
    ],
    'credit_analyst': [
        # View Assigned Data
        'VIEW_ASSIGNED_ASSESSMENTS',
        'VIEW_ASSIGNED_CUSTOMERS',
        'VIEW_ADVANCED_ANALYTICS',
        
        # Edit Assigned Data
        'EDIT_ASSIGNED_ASSESSMENTS',  # Only if status='pending_analysis' or 'under_review'
        'ADD_ANALYSIS_NOTES',
        'ADD_FRAUD_FLAGS',
        
        # Analysis Actions
        'MARK_UNDER_REVIEW',
        'COMPLETE_ANALYSIS',
        'RECOMMEND_APPROVAL',
        'RECOMMEND_REJECTION',
        'RECOMMEND_ESCALATION',
        
        # Tools Access
        'ACCESS_FRAUD_DETECTION_TOOLS',
        'ACCESS_DOCUMENT_VERIFICATION',
        'ACCESS_BEHAVIORAL_ANALYTICS',
        'RUN_CUSTOM_ANALYSIS',
        
        # Workflow
        'SUBMIT_REVIEW',
        'FLAG_FRAUD',
        'ESCALATE_TO_MANAGER',
        'VERIFY_DOCUMENTS',
        'SUBMIT_TO_MANAGER',
        'REQUEST_ADDITIONAL_DOCUMENTS',
        'FLAG_FOR_QUALITY_REVIEW'
    ]
}


# ============================================================================
# STATUS TRANSITION RULES
# ============================================================================

ALLOWED_STATUS_TRANSITIONS = {
    'draft': {
        'allowed_next': ['pending_review', 'deleted'],
        'allowed_roles': ['loan_officer', 'credit_manager', 'branch_manager'],
        'action': 'submit_for_review'
    },
    'pending_review': {
        'allowed_next': ['under_review', 'draft'],
        'allowed_roles': ['credit_analyst', 'credit_manager', 'branch_manager'],
        'action': 'start_review'
    },
    'under_review': {
        'allowed_next': ['reviewed', 'escalated', 'pending_review'],
        'allowed_roles': ['credit_analyst', 'branch_manager'],
        'action': 'complete_review'
    },
    'reviewed': {
        'allowed_next': ['pending_approval', 'under_review'],
        'allowed_roles': ['credit_analyst', 'credit_manager', 'branch_manager'],
        'action': 'submit_to_manager'
    },
    'pending_approval': {
        'allowed_next': ['approved', 'rejected', 'escalated'],
        'allowed_roles': ['credit_manager', 'branch_manager'],
        'action': 'make_decision'
    },
    'approved': {
        'allowed_next': ['rejected'],
        'allowed_roles': ['branch_manager'],
        'action': 'override_approval'
    },
    'rejected': {
        'allowed_next': ['draft', 'pending_review', 'approved'],
        'allowed_roles': ['loan_officer', 'branch_manager'],
        'action': 'resubmit_or_override'
    },
    'escalated': {
        'allowed_next': ['pending_approval', 'approved', 'rejected'],
        'allowed_roles': ['credit_manager', 'branch_manager'],
        'action': 'resolve_escalation'
    }
}


def validate_status_transition(assessment, new_status, employee):
    """
    Validate if a status transition is allowed.
    
    Args:
        assessment: CreditAssessment object
        new_status: Target status string
        employee: Employee performing the transition
        
    Returns:
        tuple: (success: bool, error_message: str)
    """
    current_status = assessment.status
    
    # Branch manager can do anything
    if employee.has_permission('ALL'):
        return True, None
    
    # Check if transition exists
    if current_status not in ALLOWED_STATUS_TRANSITIONS:
        return False, f"Current status '{current_status}' has no defined transitions"
    
    transition_rule = ALLOWED_STATUS_TRANSITIONS[current_status]
    
    # Check if new status is allowed from current
    if new_status not in transition_rule['allowed_next']:
        return False, f"Cannot transition from '{current_status}' to '{new_status}'"
    
    # Check if employee role is allowed to make this transition
    if employee.role not in transition_rule['allowed_roles']:
        return False, f"Role '{employee.role}' cannot perform this transition"
    
    # Additional checks based on role
    if employee.role == 'loan_officer' and assessment.created_by != employee.id:
        return False, "Loan officers can only transition their own assessments"
    
    if employee.role == 'credit_analyst' and assessment.assigned_to != employee.id:
        return False, "Analysts can only transition assessments assigned to them"
    
    if employee.role == 'credit_manager':
        team_ids = [e.id for e in employee.get_team_members()]
        if assessment.created_by not in team_ids and assessment.assigned_to not in team_ids:
            return False, "Credit managers can only transition their team's assessments"
    
    return True, None


def assign_assessment_to_analyst(assessment_id, loan_officer_id=None):
    """
    Auto-assign assessment to available credit analyst using workload-based algorithm.
    
    Algorithm: Workload-Based Round Robin
    1. Get active analysts in the same team
    2. Calculate workload (pending_review + under_review count)
    3. Assign to analyst with lowest workload
    4. Create notification and assignment history
    
    Returns:
        tuple: (success: bool, assigned_employee_id: int or None, message: str)
    """
    assessment = CreditAssessment.query.get(assessment_id)
    if not assessment:
        return False, None, "Assessment not found"
    
    # Get team_id from the loan officer who created the assessment
    if loan_officer_id:
        loan_officer = Employee.query.get(loan_officer_id)
        team_id = loan_officer.team_id if loan_officer else None
    else:
        creator = Employee.query.get(assessment.created_by)
        team_id = creator.team_id if creator else None
    
    # Find active credit analysts - first try same team, then any team
    analysts = []
    
    # Priority 1: Same team analysts
    if team_id:
        analysts = Employee.query.filter_by(
            role='credit_analyst',
            status='ACTIVE',
            team_id=team_id
        ).all()
    
    # Priority 2: Any available analyst (if not found in same team)
    if not analysts:
        analysts = Employee.query.filter_by(
            role='credit_analyst',
            status='ACTIVE'
        ).all()
    
    # Priority 3: Credit manager (if no analysts available)
    if not analysts:
        managers = Employee.query.filter_by(
            role='credit_manager',
            status='ACTIVE'
        ).all()
        if managers:
            analysts = managers
    
    # Priority 4: Branch manager (last resort)
    if not analysts:
        analysts = Employee.query.filter_by(
            role='branch_manager',
            status='ACTIVE'
        ).all()
    
    if not analysts:
        return False, None, "No available employees to assign"
    
    # Calculate workload for each analyst
    analyst_workloads = []
    for analyst in analysts:
        workload = CreditAssessment.query.filter(
            CreditAssessment.assigned_to == analyst.id,
            CreditAssessment.status.in_(['pending_review', 'under_review'])
        ).count()
        analyst_workloads.append((analyst, workload))
    
    # Sort by workload (ascending) then by ID for consistent ordering
    analyst_workloads.sort(key=lambda x: (x[1], x[0].id))
    
    # Assign to analyst with lowest workload
    selected_analyst = analyst_workloads[0][0]
    
    # Update assessment
    old_assigned = assessment.assigned_to
    assessment.assigned_to = selected_analyst.id
    assessment.status = 'pending_review'
    assessment.submitted_at = datetime.utcnow()
    assessment.sla_deadline = assessment.calculate_sla_deadline()
    
    # Create assignment history
    history = AssignmentHistory(
        assessment_id=assessment.id,
        assigned_from=old_assigned,
        assigned_to=selected_analyst.id,
        assignment_type='AUTO',
        reason='Workload-based auto-assignment'
    )
    db.session.add(history)
    
    # Create notification for analyst
    Notification.create(
        employee_id=selected_analyst.id,
        notification_type='ASSIGNED',
        message=f'New assessment #{assessment.id} assigned to you for review',
        assessment_id=assessment.id,
        priority='MEDIUM' if assessment.priority == 'normal' else 'HIGH'
    )
    
    # Create audit log
    AuditLog.log(
        employee_id=loan_officer_id or assessment.created_by,
        action='REASSIGN',
        entity_type='assessment',
        entity_id=assessment.id,
        after={'assigned_to': selected_analyst.id, 'status': 'pending_review'},
        details={'assignment_type': 'AUTO', 'selected_from': len(analysts)}
    )
    
    return True, selected_analyst.id, f"Assigned to {selected_analyst.full_name}"


def get_accessible_assessments(employee, branch_filter=None):
    """
    Get assessments accessible to the given employee based on their role.
    
    Args:
        employee: Employee object
        branch_filter: Optional branch_id to filter by (for admin/credit_manager)
    
    Returns: SQLAlchemy query object (not executed)
    """
    from sqlalchemy import or_
    
    def get_branch_employee_ids(branch_id):
        """Helper to get all employee IDs in a branch"""
        if not branch_id:
            return []
        return [e.id for e in Employee.query.filter_by(branch_id=branch_id, status='ACTIVE').all()]
    
    # HEAD OF BANK - Sees all, can filter by branch
    if employee.role == 'head_of_bank':
        query = CreditAssessment.query.filter(CreditAssessment.created_by.isnot(None))
        if branch_filter:
            branch_emp_ids = get_branch_employee_ids(branch_filter)
            if branch_emp_ids:
                query = query.filter(CreditAssessment.created_by.in_(branch_emp_ids))
        return query
    
    # CREDIT MANAGER - Sees all, can filter by branch (for approval workflow)
    elif employee.role == 'credit_manager':
        query = CreditAssessment.query.filter(CreditAssessment.created_by.isnot(None))
        if branch_filter:
            branch_emp_ids = get_branch_employee_ids(branch_filter)
            if branch_emp_ids:
                query = query.filter(CreditAssessment.created_by.in_(branch_emp_ids))
        return query
    
    # BRANCH MANAGER - Sees ONLY their branch's assessments
    elif employee.role == 'branch_manager':
        if not employee.branch_id:
            return CreditAssessment.query.filter_by(id=None)  # Empty query
        branch_emp_ids = get_branch_employee_ids(employee.branch_id)
        if not branch_emp_ids:
            return CreditAssessment.query.filter_by(id=None)  # Empty query
        return CreditAssessment.query.filter(
            CreditAssessment.created_by.in_(branch_emp_ids)
        )
    
    # LOAN OFFICER - Sees only their own created assessments
    elif employee.role == 'loan_officer':
        return CreditAssessment.query.filter_by(created_by=employee.id)
    
    # CREDIT ANALYST - Sees all assessments assigned to them (current + past)
    elif employee.role == 'credit_analyst':
        return CreditAssessment.query.filter_by(assigned_to=employee.id)
    
    # Default: empty query for unknown roles
    return CreditAssessment.query.filter_by(id=None)


def initialize_employee_permissions(role):
    """
    Get default permissions JSON for a role.
    
    Args:
        role: Role string (branch_manager, credit_manager, etc.)
        
    Returns:
        JSON string of permissions array
    """
    permissions = ROLE_PERMISSIONS.get(role, [])
    return json.dumps(permissions)


# ============================================================================
# ANALYTICS FUNCTIONS FOR DASHBOARDS
# ============================================================================

def calculate_approval_rate(employee_id=None, team_id=None, days=30):
    """
    Calculate approval rate for employee, team, or entire branch.
    
    Returns: {
        'total_assessments': int,
        'approved': int,
        'rejected': int,
        'pending': int,
        'approval_rate': float (0-100),
        'rejection_rate': float (0-100)
    }
    """
    from sqlalchemy import func
    
    # Base query
    query = CreditAssessment.query.filter(
        CreditAssessment.created_by.isnot(None),  # Only bank assessments
        CreditAssessment.assessment_date >= datetime.utcnow() - timedelta(days=days)
    )
    
    # Filter by employee or team
    if employee_id:
        query = query.filter(CreditAssessment.created_by == employee_id)
    elif team_id:
        team_members = Employee.query.filter_by(team_id=team_id).all()
        team_ids = [e.id for e in team_members]
        query = query.filter(CreditAssessment.created_by.in_(team_ids))
    
    total = query.count()
    approved = query.filter(CreditAssessment.status == 'approved').count()
    rejected = query.filter(CreditAssessment.status == 'rejected').count()
    pending = query.filter(CreditAssessment.status.in_(['draft', 'pending_review', 'under_review', 'reviewed', 'pending_approval'])).count()
    
    return {
        'total_assessments': total,
        'approved': approved,
        'rejected': rejected,
        'pending': pending,
        'approval_rate': round((approved / total * 100) if total > 0 else 0, 1),
        'rejection_rate': round((rejected / total * 100) if total > 0 else 0, 1)
    }


def calculate_portfolio_risk(employee_id=None, team_id=None):
    """
    Calculate portfolio risk distribution.
    
    Returns: {
        'total_assessments': int,
        'low_risk_count': int,
        'medium_risk_count': int,
        'high_risk_count': int,
        'low_risk_percentage': float,
        'medium_risk_percentage': float,
        'high_risk_percentage': float,
        'avg_credit_score': float,
        'risk_score': float (0-100, higher = riskier portfolio)
    }
    """
    query = CreditAssessment.query.filter(CreditAssessment.created_by.isnot(None))
    
    if employee_id:
        query = query.filter(CreditAssessment.created_by == employee_id)
    elif team_id:
        team_members = Employee.query.filter_by(team_id=team_id).all()
        team_ids = [e.id for e in team_members]
        query = query.filter(CreditAssessment.created_by.in_(team_ids))
    
    assessments = query.all()
    total = len(assessments)
    
    if total == 0:
        return {
            'total_assessments': 0,
            'low_risk_count': 0,
            'medium_risk_count': 0,
            'high_risk_count': 0,
            'low_risk_percentage': 0,
            'medium_risk_percentage': 0,
            'high_risk_percentage': 0,
            'avg_credit_score': 0,
            'risk_score': 0
        }
    
    low_risk = sum(1 for a in assessments if a.risk_category == 'Low')
    medium_risk = sum(1 for a in assessments if a.risk_category == 'Medium')
    high_risk = sum(1 for a in assessments if a.risk_category == 'High')
    avg_score = sum(a.credit_score for a in assessments) / total
    
    # Risk score: weighted combination (higher = riskier)
    risk_score = ((high_risk * 100) + (medium_risk * 50) + (low_risk * 10)) / total
    
    return {
        'total_assessments': total,
        'low_risk_count': low_risk,
        'medium_risk_count': medium_risk,
        'high_risk_count': high_risk,
        'low_risk_percentage': round(low_risk / total * 100, 1),
        'medium_risk_percentage': round(medium_risk / total * 100, 1),
        'high_risk_percentage': round(high_risk / total * 100, 1),
        'avg_credit_score': round(avg_score, 0),
        'risk_score': round(risk_score, 1)
    }


def calculate_potential_revenue(employee_id=None, team_id=None):
    """
    Calculate potential revenue based on assessment outcomes.
    Assumes: Low risk = ₹50,000, Medium = ₹25,000, High = ₹5,000 estimated profit
    
    Returns: {
        'total_potential': float,
        'approved_revenue': float,
        'pipeline_revenue': float
    }
    """
    REVENUE_FACTORS = {'Low': 50000, 'Medium': 25000, 'High': 5000}
    
    query = CreditAssessment.query.filter(CreditAssessment.created_by.isnot(None))
    
    if employee_id:
        query = query.filter(CreditAssessment.created_by == employee_id)
    elif team_id:
        team_members = Employee.query.filter_by(team_id=team_id).all()
        team_ids = [e.id for e in team_members]
        query = query.filter(CreditAssessment.created_by.in_(team_ids))
    
    assessments = query.all()
    
    total_potential = sum(REVENUE_FACTORS.get(a.risk_category, 0) for a in assessments)
    approved_revenue = sum(REVENUE_FACTORS.get(a.risk_category, 0) for a in assessments if a.status == 'approved')
    pipeline_revenue = sum(REVENUE_FACTORS.get(a.risk_category, 0) for a in assessments if a.status in ['pending_review', 'under_review', 'reviewed', 'pending_approval'])
    
    return {
        'total_potential': total_potential,
        'approved_revenue': approved_revenue,
        'pipeline_revenue': pipeline_revenue
    }


def get_weekly_assessment_trend(employee_id=None, team_id=None, weeks=12):
    """
    Get weekly assessment count trend.
    
    Returns: {
        'labels': ['Week 1', 'Week 2', ...],
        'data': [15, 23, 19, ...]
    }
    """
    labels = []
    data = []
    
    for i in range(weeks - 1, -1, -1):
        week_start = datetime.utcnow() - timedelta(weeks=i+1)
        week_end = datetime.utcnow() - timedelta(weeks=i)
        
        query = CreditAssessment.query.filter(
            CreditAssessment.created_by.isnot(None),
            CreditAssessment.assessment_date >= week_start,
            CreditAssessment.assessment_date < week_end
        )
        
        if employee_id:
            query = query.filter(CreditAssessment.created_by == employee_id)
        elif team_id:
            team_members = Employee.query.filter_by(team_id=team_id).all()
            team_ids = [e.id for e in team_members]
            query = query.filter(CreditAssessment.created_by.in_(team_ids))
        
        count = query.count()
        labels.append(f'Week {weeks - i}')
        data.append(count)
    
    return {'labels': labels, 'data': data}


def calculate_officer_productivity(employee_id):
    """
    Calculate productivity metrics for an officer.
    
    Returns: {
        'assessments_today': int,
        'assessments_this_week': int,
        'assessments_this_month': int,
        'avg_processing_time_minutes': float,
        'productivity_score': float (0-100)
    }
    """
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    
    base_query = CreditAssessment.query.filter(CreditAssessment.created_by == employee_id)
    
    today_count = base_query.filter(CreditAssessment.assessment_date >= today).count()
    week_count = base_query.filter(CreditAssessment.assessment_date >= week_start).count()
    month_count = base_query.filter(CreditAssessment.assessment_date >= month_start).count()
    
    # Get avg processing time
    employee = Employee.query.get(employee_id)
    avg_time = employee.avg_processing_time_minutes if employee else 0
    
    # Calculate productivity score (based on assessments vs target)
    daily_target = 5
    productivity_score = min(100, (today_count / daily_target) * 100) if daily_target > 0 else 0
    
    return {
        'assessments_today': today_count,
        'assessments_this_week': week_count,
        'assessments_this_month': month_count,
        'avg_processing_time_minutes': round(avg_time, 1),
        'productivity_score': round(productivity_score, 1)
    }


# ============================================================================
# ROLE-SPECIFIC DASHBOARD STATS FUNCTIONS
# ============================================================================

def get_head_of_bank_stats(employee):
    """Get executive dashboard stats for head of bank - sees ALL branches"""
    # Get all branches
    branches = Branch.query.filter_by(status='active').all()
    
    # Branch-wise performance
    branch_stats = []
    for branch in branches:
        branch_employees = Employee.query.filter_by(branch_id=branch.id, status='ACTIVE').all()
        branch_emp_ids = [e.id for e in branch_employees]
        
        branch_assessments = CreditAssessment.query.filter(
            CreditAssessment.created_by.in_(branch_emp_ids)
        ).all() if branch_emp_ids else []
        
        approved = len([a for a in branch_assessments if a.status == 'approved'])
        total = len(branch_assessments)
        
        branch_stats.append({
            'branch': branch,
            'employee_count': len(branch_employees),
            'assessment_count': total,
            'approved_count': approved,
            'approval_rate': round((approved / total * 100) if total > 0 else 0, 1)
        })
    
    return {
        'total_branches': Branch.query.count(),
        'active_branches': Branch.query.filter_by(status='active').count(),
        'total_employees': Employee.query.filter_by(status='ACTIVE').count(),
        'total_assessments': CreditAssessment.query.filter(CreditAssessment.created_by.isnot(None)).count(),
        'approval_rate': calculate_approval_rate(),
        'portfolio_risk': calculate_portfolio_risk(),
        'revenue': calculate_potential_revenue(),
        'trend': get_weekly_assessment_trend(),
        'branch_stats': branch_stats,
        'pending_escalations': CreditAssessment.query.filter_by(status='escalated').count(),
        'recent_assessments': CreditAssessment.query.filter(
            CreditAssessment.created_by.isnot(None)
        ).order_by(CreditAssessment.assessment_date.desc()).limit(15).all()
    }


def get_branch_manager_stats(employee):
    """Get dashboard stats for branch manager - filtered to their branch"""
    branch_id = employee.branch_id
    
    # Get employees in this branch
    branch_employees = Employee.query.filter_by(branch_id=branch_id, status='ACTIVE').all() if branch_id else []
    branch_emp_ids = [e.id for e in branch_employees]
    
    # Base query for branch assessments
    if branch_emp_ids:
        branch_query = CreditAssessment.query.filter(CreditAssessment.created_by.in_(branch_emp_ids))
    else:
        branch_query = CreditAssessment.query.filter(CreditAssessment.created_by.isnot(None))
    
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    return {
        'approval_rate': calculate_approval_rate(),
        'portfolio_risk': calculate_portfolio_risk(),
        'revenue': calculate_potential_revenue(),
        'trend': get_weekly_assessment_trend(),
        'total_employees': len(branch_employees) if branch_id else Employee.query.filter_by(status='ACTIVE').count(),
        'pending_overrides': CreditAssessment.query.filter_by(status='escalated').count(),
        'today_assessments': branch_query.filter(CreditAssessment.assessment_date >= today).count(),
        'recent_assessments': branch_query.order_by(CreditAssessment.assessment_date.desc()).limit(10).all()
    }


def get_credit_manager_stats(employee):
    """Get dashboard stats for credit manager"""
    team_id = employee.team_id
    return {
        'approval_rate': calculate_approval_rate(team_id=team_id),
        'portfolio_risk': calculate_portfolio_risk(team_id=team_id),
        'trend': get_weekly_assessment_trend(team_id=team_id),
        'pending_approval': CreditAssessment.query.filter(
            CreditAssessment.status == 'pending_approval'
        ).count(),
        'escalated': CreditAssessment.query.filter_by(status='escalated').count(),
        'reviewed_today': CreditAssessment.query.filter(
            CreditAssessment.reviewed_at >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        ).count(),
        'queue': CreditAssessment.query.filter(
            CreditAssessment.status.in_(['reviewed', 'pending_approval'])
        ).order_by(CreditAssessment.assessment_date.desc()).limit(10).all()
    }


def get_loan_officer_stats(employee):
    """Get dashboard stats for loan officer"""
    return {
        'productivity': calculate_officer_productivity(employee.id),
        'my_drafts': CreditAssessment.query.filter_by(
            created_by=employee.id, status='draft'
        ).count(),
        'my_pending': CreditAssessment.query.filter(
            CreditAssessment.created_by == employee.id,
            CreditAssessment.status.in_(['pending_review', 'under_review', 'reviewed', 'pending_approval'])
        ).count(),
        'my_approved': CreditAssessment.query.filter_by(
            created_by=employee.id, status='approved'
        ).count(),
        'my_rejected': CreditAssessment.query.filter_by(
            created_by=employee.id, status='rejected'
        ).count(),
        'recent_assessments': CreditAssessment.query.filter_by(
            created_by=employee.id
        ).order_by(CreditAssessment.assessment_date.desc()).limit(10).all()
    }


def get_credit_analyst_stats(employee):
    """Get dashboard stats for credit analyst"""
    return {
        'assigned_pending': CreditAssessment.query.filter_by(
            assigned_to=employee.id, status='pending_review'
        ).count(),
        'under_review': CreditAssessment.query.filter_by(
            assigned_to=employee.id, status='under_review'
        ).count(),
        'completed_today': CreditAssessment.query.filter(
            CreditAssessment.reviewed_by == employee.id,
            CreditAssessment.reviewed_at >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        ).count(),
        'queue': CreditAssessment.query.filter(
            CreditAssessment.assigned_to == employee.id,
            CreditAssessment.status.in_(['pending_review', 'under_review'])
        ).order_by(CreditAssessment.assessment_date.asc()).all(),
        'productivity': calculate_officer_productivity(employee.id)
    }



# Authentication decorators
def login_required_public(f):
    """Require public portal authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'customer_id' not in session:
            return redirect(url_for('landing'))
        return f(*args, **kwargs)
    return decorated_function

def login_required_bank(f):
    """Require bank portal authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'employee_id' not in session:
            return redirect(url_for('bank_login'))
        return f(*args, **kwargs)
    return decorated_function

def permission_required(*required_permissions, require_all=False):
    """
    Require specific permission(s) for bank users.
    
    Args:
        *required_permissions: Permission strings to check
        require_all: If True, user must have ALL permissions. If False, any one is sufficient.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'employee_id' not in session:
                return redirect(url_for('bank_login'))
            
            employee = Employee.query.get(session['employee_id'])
            if not employee:
                session.clear()
                return redirect(url_for('bank_login'))
            
            # Check if employee is still active
            if employee.status != 'ACTIVE':
                session.clear()
                flash('Your account has been deactivated. Please contact administrator.', 'error')
                return redirect(url_for('bank_login'))
            
            permissions = json.loads(employee.permissions) if employee.permissions else []
            
            # Branch manager with ALL bypasses checks
            if 'ALL' in permissions:
                return f(*args, **kwargs)
            
            # Check required permissions
            if require_all:
                has_permission = all(p in permissions for p in required_permissions)
            else:
                has_permission = any(p in permissions for p in required_permissions)
            
            if not has_permission:
                # Log unauthorized access attempt
                AuditLog.log(
                    employee_id=employee.id,
                    action='UNAUTHORIZED_ACCESS',
                    entity_type='route',
                    details={
                        'route': request.endpoint,
                        'required_permissions': list(required_permissions),
                        'user_permissions': permissions
                    },
                    ip=request.remote_addr,
                    user_agent=request.user_agent.string[:500] if request.user_agent else None
                )
                db.session.commit()
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_current_employee():
    """Get current logged in employee or None"""
    if 'employee_id' not in session:
        return None
    return Employee.query.get(session['employee_id'])



# Error Handlers
@app.errorhandler(403)
def forbidden(e):
    return render_template('403.html'), 403

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

# Routes - Landing Page
@app.route('/')
def landing():
    """Landing page with portal selection"""
    return render_template('landing.html')

# Routes - Public Portal Authentication
@app.route('/auth/google')
def google_login():
    """Initiate Google OAuth"""
    if google is None:
        flash('Google login is not configured. Please contact the administrator or try again later.', 'error')
        return redirect(url_for('landing'))
    try:
        redirect_uri = url_for('google_callback', _external=True)
        return google.authorize_redirect(redirect_uri)
    except Exception as e:
        flash(f'Unable to connect to Google: {str(e)}', 'error')
        return redirect(url_for('landing'))

@app.route('/auth/google/callback')
def google_callback():
    """Handle Google OAuth callback"""
    if google is None:
        flash('Google login is not configured.', 'error')
        return redirect(url_for('landing'))
    try:
        token = google.authorize_access_token()
        
        # Use userinfo endpoint instead of deprecated parse_id_token
        user_info = token.get('userinfo')
        if not user_info:
            # Fallback: fetch userinfo from Google
            resp = google.get('https://openidconnect.googleapis.com/v1/userinfo')
            user_info = resp.json()
        
        # Find or create customer
        customer = Customer.query.filter_by(google_id=user_info['sub']).first()
        
        if not customer:
            customer = Customer(
                google_id=user_info['sub'],
                email=user_info.get('email', ''),
                full_name=user_info.get('name', 'User'),
                profile_picture=user_info.get('picture'),
                is_verified=user_info.get('email_verified', False)
            )
            db.session.add(customer)
            db.session.commit()
        else:
            # Update existing customer info
            customer.full_name = user_info.get('name', customer.full_name)
            customer.profile_picture = user_info.get('picture')
            db.session.commit()
        
        # Set session
        session['customer_id'] = customer.id
        session['customer_name'] = customer.full_name
        session['customer_email'] = customer.email
        session['portal_type'] = 'public'
        
        flash(f'Welcome, {customer.full_name}!', 'success')
        return redirect(url_for('public_dashboard'))
        
    except Exception as e:
        print(f"Google OAuth error: {e}")
        flash(f'Login failed: {str(e)}', 'error')
        return redirect(url_for('landing'))

@app.route('/auth/logout')
def logout():
    """Logout from public portal"""
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('landing'))

# Routes - Public Portal
@app.route('/public/dashboard')
@login_required_public
def public_dashboard():
    """Public dashboard"""
    customer = Customer.query.get(session['customer_id'])
    
    # Get latest assessment
    latest_assessment = None
    if customer.users:
        latest_user = customer.users[-1]  # Most recent user
        latest_assessment = CreditAssessment.query.filter_by(
            user_id=latest_user.id,
            processed_by=None  # Public assessments only
        ).order_by(CreditAssessment.assessment_date.desc()).first()
    
    # Get document count
    document_count = DocumentUpload.query.filter_by(customer_id=customer.id).count()
    
    # Get score history
    score_history = ScoreHistory.query.filter_by(customer_id=customer.id).order_by(
        ScoreHistory.created_at.desc()
    ).limit(5).all()
    
    return render_template('public/dashboard.html',
                         customer=customer,
                         latest_assessment=latest_assessment,
                         document_count=document_count,
                         score_history=score_history)

@app.route('/public/assessment', methods=['GET', 'POST'])
@login_required_public
def public_assessment():
    """Public assessment form with document analysis"""
    if request.method == 'GET':
        return render_template('public/assessment_form.html')
    
    try:
        # Get form data
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        pan_card = request.form.get('pan_card', '').strip()
        
        # Financial data
        monthly_income = float(request.form.get('monthly_income', 0))
        monthly_expenses = float(request.form.get('monthly_expenses', 0))
        income_std_dev = float(request.form.get('income_std_dev', 0))
        upi_transactions = int(request.form.get('upi_transactions', 0))
        bill_payment_streak = int(request.form.get('bill_payment_streak', 0))
        digital_months = int(request.form.get('digital_months', 0))
        savings_amount = float(request.form.get('savings_amount', 0))
        business_revenue = float(request.form.get('business_revenue', 0))
        business_expenses = float(request.form.get('business_expenses', 0))
        
        # Validation
        if not name or not phone or monthly_income <= 0:
            flash('Please fill all required fields correctly.', 'error')
            return render_template('public/assessment_form.html')
        
        # Collect uploaded documents
        doc_files = {}
        doc_field_names = [
            'doc_aadhaar', 'doc_pan', 'doc_bank_statement',
            'doc_salary_slip', 'doc_itr', 'doc_utility_bill',
            'doc_gst', 'doc_investment', 'doc_employment'
        ]
        
        for field_name in doc_field_names:
            if field_name in request.files:
                file = request.files[field_name]
                if file and file.filename:
                    doc_files[field_name] = file
        
        # Validate mandatory documents
        mandatory_fields = ['doc_aadhaar', 'doc_pan', 'doc_bank_statement']
        missing_docs = [f for f in mandatory_fields if f not in doc_files]
        
        if missing_docs:
            flash('Please upload all mandatory documents (Aadhaar, PAN, Bank Statement).', 'error')
            return render_template('public/assessment_form.html')
        
        customer = Customer.query.get(session['customer_id'])
        
        # Create user
        user = User(
            name=name,
            phone=phone,
            email=email or None,
            pan_card=pan_card or None,
            customer_id=customer.id
        )
        db.session.add(user)
        db.session.flush()
        
        # Create financial profile
        profile = FinancialProfile(
            user_id=user.id,
            monthly_income=monthly_income,
            monthly_expenses=monthly_expenses,
            income_std_dev=income_std_dev,
            upi_transaction_count=upi_transactions,
            bill_payment_streak=bill_payment_streak,
            digital_activity_months=digital_months,
            savings_amount=savings_amount,
            business_revenue=business_revenue,
            business_expenses=business_expenses
        )
        db.session.add(profile)
        db.session.flush()
        
        # Process documents with analyzer
        doc_results = document_analyzer.analyze_all_documents(
            doc_files, 
            app.config['UPLOAD_FOLDER']
        )
        
        # Calculate behavioral features
        behavioral_features = ml_model.calculate_behavioral_features(
            monthly_income, monthly_expenses, income_std_dev,
            upi_transactions, bill_payment_streak, digital_months,
            savings_amount, business_revenue, business_expenses
        )
        
        # Calculate document-derived features
        doc_features = ml_model.calculate_document_features(
            doc_results.get('combined_features', {}),
            monthly_income,
            monthly_expenses
        )
        
        # Combine all features
        all_features = {**behavioral_features, **doc_features}
        
        # Get ML prediction with documents
        ml_prediction = ml_model.predict(all_features, doc_results)
        
        credit_score = ml_prediction['credit_score']
        risk_category = ml_prediction['risk_category']
        confidence_level = ml_prediction['confidence_level']
        
        # Create assessment
        assessment = CreditAssessment(
            user_id=user.id,
            profile_id=profile.id,
            credit_score=credit_score,
            risk_category=risk_category,
            repayment_probability=ml_prediction['repayment_probability'],
            features_json=json.dumps({
                'behavioral': behavioral_features,
                'document': doc_features,
                'confidence_level': confidence_level,
                'model_used': ml_prediction.get('model_used', 'XGBoost')
            }),
            document_bonus=0,  # No longer using bonus system
            processed_by=None  # Public assessment
        )
        db.session.add(assessment)
        db.session.flush()
        
        # Add to score history
        score_entry = ScoreHistory(
            customer_id=customer.id,
            assessment_id=assessment.id,
            score=credit_score,
            risk_category=risk_category,
            document_count=doc_results.get('total_documents', 0)
        )
        db.session.add(score_entry)
        
        # Create improvement plan
        improvement_suggestions = {
            'immediate': [],
            'short_term': [], 
            'long_term': []
        }
        
        if behavioral_features['payment_consistency_score'] < 0.5:
            improvement_suggestions['immediate'].append("Set up auto-pay for bills")
        if behavioral_features['digital_activity_score'] < 0.3:
            improvement_suggestions['immediate'].append("Increase UPI usage")
        if behavioral_features['savings_discipline_ratio'] < 0.3:
            improvement_suggestions['short_term'].append("Build 3-month emergency fund")
        if doc_features.get('doc_financial_health_score', 0.5) < 0.4:
            improvement_suggestions['short_term'].append("Reduce overdrafts and bounced transactions")
        
        improvement_plan = ImprovementPlan(
            customer_id=customer.id,
            assessment_id=assessment.id,
            current_score=credit_score,
            target_score=min(900, credit_score + 100),
            suggestions_json=json.dumps(improvement_suggestions)
        )
        db.session.add(improvement_plan)
        
        db.session.commit()
        
        flash(f'Assessment completed! Score: {credit_score} ({risk_category}) - Confidence: {int(confidence_level*100)}%', 'success')
        return redirect(url_for('public_result', id=assessment.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Assessment failed: {str(e)}', 'error')
        return render_template('public/assessment_form.html')

@app.route('/public/result/<int:id>')
@login_required_public
def public_result(id):
    """Show assessment result"""
    assessment = CreditAssessment.query.get_or_404(id)
    
    # Verify ownership (public assessments only)
    if assessment.processed_by is not None:
        abort(404)
    
    if assessment.user.customer_id != session['customer_id']:
        abort(403)
    
    # Parse features (handle both old and new format)
    raw_features = json.loads(assessment.features_json)
    
    # If new format with behavioral/document keys, flatten it
    if 'behavioral' in raw_features:
        features = {**raw_features['behavioral']}
        features['confidence_level'] = raw_features.get('confidence_level', 0.75)
        features['model_used'] = raw_features.get('model_used', 'XGBoost')
        if 'document' in raw_features:
            features.update(raw_features['document'])
    else:
        # Old format - use as-is
        features = raw_features
    
    # Get improvement plan
    improvement_plan = ImprovementPlan.query.filter_by(assessment_id=assessment.id).first()
    suggestions = json.loads(improvement_plan.suggestions_json) if improvement_plan else {}
    
    return render_template('public/result.html',
                         assessment=assessment,
                         features=features,
                         suggestions=suggestions)

@app.route('/public/upload-documents', methods=['GET', 'POST'])
@login_required_public
def public_upload_documents():
    """Upload documents"""
    if request.method == 'GET':
        # Show existing documents
        customer = Customer.query.get(session['customer_id'])
        documents = DocumentUpload.query.filter_by(customer_id=customer.id).order_by(
            DocumentUpload.uploaded_at.desc()
        ).all()
        
        return render_template('public/upload_documents.html', documents=documents)
    
    try:
        document_type = request.form.get('document_type')
        file = request.files.get('document_file')
        
        if not document_type or not file:
            flash('Please select document type and file.', 'error')
            return redirect(url_for('public_upload_documents'))
        
        customer = Customer.query.get(session['customer_id'])
        
        # Analyze document
        analysis_result = document_analyzer.analyze_document(
            file, document_type, app.config['UPLOAD_FOLDER']
        )
        
        if not analysis_result['success']:
            flash(f"Upload failed: {analysis_result['error']}", 'error')
            return redirect(url_for('public_upload_documents'))
        
        # Save document record
        document = DocumentUpload(
            customer_id=customer.id,
            document_type=document_type,
            file_path=analysis_result['file_path'],
            file_size=analysis_result['file_size'],
            verified_status=analysis_result['verified_status'],
            ai_verification_score=analysis_result['ai_verification_score'],
            analysis_json=analysis_result['analysis_json']
        )
        db.session.add(document)
        db.session.commit()
        
        flash(f'Document uploaded successfully! Verification score: {analysis_result["ai_verification_score"]:.0f}%', 'success')
        return redirect(url_for('public_upload_documents'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Upload failed: {str(e)}', 'error')
        return redirect(url_for('public_upload_documents'))

@app.route('/public/history')
@login_required_public
def public_history():
    """Score history"""
    customer = Customer.query.get(session['customer_id'])
    
    score_history = ScoreHistory.query.filter_by(customer_id=customer.id).order_by(
        ScoreHistory.created_at.desc()
    ).all()
    
    return render_template('public/history.html', score_history=score_history)

@app.route('/public/download-report/<int:id>')
@login_required_public
def public_download_report(id):
    """Download PDF report - BANK-GRADE VERSION"""
    from bank_grade_pdf_generator import generate_bank_grade_report
    
    assessment = CreditAssessment.query.get_or_404(id)
    
    # Verify ownership (public assessments only)
    if assessment.processed_by is not None or assessment.user.customer_id != session['customer_id']:
        abort(403)
    
    try:
        # Generate professional bank-grade PDF
        temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        pdf_path = generate_bank_grade_report(assessment, assessment.user, temp_pdf.name)
        
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=f'creditbridge_report_{assessment.id}.pdf',
            mimetype='application/pdf'
        )
        
    except Exception as e:
        flash(f'Report generation failed: {str(e)}', 'error')
        return redirect(url_for('public_result', id=id))

# Routes - Bank Portal Authentication
@app.route('/bank/login', methods=['GET', 'POST'])
def bank_login():
    """Bank staff login"""
    if request.method == 'GET':
        return render_template('bank/login.html')
    
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    
    if not username or not password:
        flash('Please enter username and password.', 'error')
        return render_template('bank/login.html')
    
    employee = Employee.query.filter_by(username=username).first()
    
    if employee and check_password_hash(employee.password_hash, password):
        # Set session
        session['employee_id'] = employee.id
        session['employee_name'] = employee.full_name
        session['employee_role'] = employee.role
        session['portal_type'] = 'bank'
        
        flash(f'Welcome {employee.full_name}!', 'success')
        return redirect(url_for('bank_dashboard'))
    else:
        flash('Invalid credentials.', 'error')
        return render_template('bank/login.html')

@app.route('/bank/logout')
def bank_logout():
    """Bank logout"""
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('landing'))

@app.route('/bank/document/<int:doc_id>')
@login_required_bank
def bank_view_document(doc_id):
    """Serve uploaded document to authorized bank employees"""
    document = DocumentUpload.query.get_or_404(doc_id)
    
    # Get employee and check access
    employee = Employee.query.get(session.get('employee_id'))
    if not employee:
        abort(403)
    
    # Find any assessment related to this document's user
    assessment = None
    if document.user_id:
        assessment = CreditAssessment.query.filter_by(user_id=document.user_id).first()
    
    # If no assessment found by user_id, try finding through customer_id
    if not assessment and document.customer_id:
        # Find user linked to this customer and get their assessment
        user = User.query.filter_by(customer_id=document.customer_id).first()
        if user:
            assessment = CreditAssessment.query.filter_by(user_id=user.id).first()
    
    # Check if employee has access to view this document
    has_access = False
    
    if employee.has_permission('ALL') or employee.has_permission('VIEW_ALL_ASSESSMENTS'):
        has_access = True
    elif employee.role in ['Branch Manager', 'Credit Manager', 'Credit Analyst', 'branch_manager', 'credit_manager', 'credit_analyst', 'head_of_bank']:
        has_access = True
    elif assessment:
        if assessment.assigned_to == employee.id or assessment.created_by == employee.id:
            has_access = True
    
    if not has_access:
        abort(403)
    
    # Serve the file
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(document.file_path))
    if not os.path.exists(file_path):
        # Try alternative path structure
        file_path = document.file_path
    
    if not os.path.exists(file_path):
        abort(404)
    
    return send_file(file_path, as_attachment=False)

# Routes - Bank Portal
@app.route('/bank/dashboard')
@login_required_bank
def bank_dashboard():
    """Role-based bank dashboard"""
    employee = Employee.query.get(session['employee_id'])
    
    if not employee:
        session.clear()
        return redirect(url_for('bank_login'))
    
    # Update last login
    employee.last_login = datetime.utcnow()
    db.session.commit()
    
    # Get role-specific stats and template
    role = employee.role.lower().replace(' ', '_')  # Normalize role name
    
    if role == 'head_of_bank':
        stats = get_head_of_bank_stats(employee)
        template = 'bank/dashboard_head_of_bank.html'
    elif role == 'branch_manager':
        stats = get_branch_manager_stats(employee)
        template = 'bank/dashboard_branch_manager.html'
    elif role == 'credit_manager':
        stats = get_credit_manager_stats(employee)
        template = 'bank/dashboard_credit_manager.html'
    elif role == 'loan_officer':
        stats = get_loan_officer_stats(employee)
        template = 'bank/dashboard_loan_officer.html'
    elif role == 'credit_analyst':
        stats = get_credit_analyst_stats(employee)
        template = 'bank/dashboard_credit_analyst.html'
    else:
        # Default fallback - use branch manager view for unknown roles
        stats = get_branch_manager_stats(employee)
        template = 'bank/dashboard.html'
    
    # Check if template exists, fallback to default
    try:
        return render_template(template, stats=stats, employee=employee)
    except:
        # Fallback to default dashboard if role-specific template doesn't exist
        # Get basic stats for fallback
        total_assessments = CreditAssessment.query.filter(CreditAssessment.created_by.isnot(None)).count()
        today_assessments = CreditAssessment.query.filter(
            CreditAssessment.created_by.isnot(None),
            CreditAssessment.assessment_date >= datetime.utcnow().date()
        ).count()
        
        low_risk = CreditAssessment.query.filter(
            CreditAssessment.created_by.isnot(None),
            CreditAssessment.risk_category == 'Low'
        ).count()
        medium_risk = CreditAssessment.query.filter(
            CreditAssessment.created_by.isnot(None),
            CreditAssessment.risk_category == 'Medium'
        ).count()
        high_risk = CreditAssessment.query.filter(
            CreditAssessment.created_by.isnot(None),
            CreditAssessment.risk_category == 'High'
        ).count()
        
        recent_assessments = CreditAssessment.query.filter(
            CreditAssessment.created_by.isnot(None)
        ).order_by(CreditAssessment.assessment_date.desc()).limit(10).all()
        
        fallback_stats = {
            'total_assessments': total_assessments,
            'today_assessments': today_assessments,
            'risk_distribution': {
                'low': low_risk,
                'medium': medium_risk,
                'high': high_risk
            }
        }
        
        return render_template('bank/dashboard.html', stats=fallback_stats, recent_assessments=recent_assessments, employee=employee)


@app.route('/bank/assessment/new', methods=['GET', 'POST'])
@login_required_bank
def bank_assessment_new():
    """Create new bank assessment - ONLY Loan Officers can create"""
    employee = Employee.query.get(session['employee_id'])
    
    # Only Loan Officers can create assessments
    if not employee or employee.role != 'loan_officer':
        flash('Only Loan Officers can create new assessments.', 'error')
        return redirect(url_for('bank_dashboard'))
    
    if request.method == 'GET':
        return render_template('bank/assessment_form.html')
    
    try:
        # Get form data
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        pan_card = request.form.get('pan_card', '').strip()
        
        monthly_income = float(request.form.get('monthly_income', 0))
        monthly_expenses = float(request.form.get('monthly_expenses', 0))
        income_std_dev = float(request.form.get('income_std_dev', 0))
        upi_transactions = int(request.form.get('upi_transactions', 0))
        bill_payment_streak = int(request.form.get('bill_payment_streak', 0))
        digital_months = int(request.form.get('digital_months', 0))
        savings_amount = float(request.form.get('savings_amount', 0))
        business_revenue = float(request.form.get('business_revenue', 0))
        business_expenses = float(request.form.get('business_expenses', 0))
        
        if not name or not phone or monthly_income <= 0:
            flash('Please fill all required fields correctly.', 'error')
            return render_template('bank/assessment_form.html')
        
        # Collect uploaded documents
        doc_files = {}
        doc_field_names = [
            'doc_aadhaar', 'doc_pan', 'doc_bank_statement',
            'doc_salary_slip', 'doc_itr', 'doc_utility_bill',
            'doc_gst', 'doc_property', 'doc_rent', 'doc_investment',
            'doc_loan', 'doc_business', 'doc_employment'
        ]
        
        for field_name in doc_field_names:
            if field_name in request.files:
                file = request.files[field_name]
                if file and file.filename:
                    doc_files[field_name] = file
        
        # Validate mandatory documents
        mandatory_fields = ['doc_aadhaar', 'doc_pan', 'doc_bank_statement']
        missing_docs = [f for f in mandatory_fields if f not in doc_files]
        
        if missing_docs:
            flash('Please upload all mandatory documents (Aadhaar, PAN, Bank Statement).', 'error')
            return render_template('bank/assessment_form.html')
        
        # Create user
        user = User(
            name=name,
            phone=phone,
            email=email or None,
            pan_card=pan_card or None,
            customer_id=None
        )
        db.session.add(user)
        db.session.flush()
        
        # Create financial profile
        profile = FinancialProfile(
            user_id=user.id,
            monthly_income=monthly_income,
            monthly_expenses=monthly_expenses,
            income_std_dev=income_std_dev,
            upi_transaction_count=upi_transactions,
            bill_payment_streak=bill_payment_streak,
            digital_activity_months=digital_months,
            savings_amount=savings_amount,
            business_revenue=business_revenue,
            business_expenses=business_expenses
        )
        db.session.add(profile)
        db.session.flush()
        
        # Process documents with analyzer
        doc_results = document_analyzer.analyze_all_documents(
            doc_files, 
            app.config['UPLOAD_FOLDER']
        )
        
        # Calculate behavioral features
        behavioral_features = ml_model.calculate_behavioral_features(
            monthly_income, monthly_expenses, income_std_dev,
            upi_transactions, bill_payment_streak, digital_months,
            savings_amount, business_revenue, business_expenses
        )
        
        # Calculate document-derived features
        doc_features = ml_model.calculate_document_features(
            doc_results.get('combined_features', {}),
            monthly_income,
            monthly_expenses
        )
        
        # Combine all features
        all_features = {**behavioral_features, **doc_features}
        
        # Get ML prediction with documents
        ml_prediction = ml_model.predict(all_features, doc_results)
        
        credit_score = ml_prediction['credit_score']
        risk_category = ml_prediction['risk_category']
        confidence_level = ml_prediction['confidence_level']
        
        # Store document analysis results
        doc_analysis_json = {
            'total_documents': doc_results.get('total_documents', 0),
            'verified_documents': doc_results.get('verified_documents', 0),
            'all_mandatory_uploaded': doc_results.get('all_mandatory_uploaded', False),
            'cross_verification': doc_results.get('cross_verification', {}),
            'combined_features': doc_results.get('combined_features', {})
        }
        
        # Create assessment
        assessment = CreditAssessment(
            user_id=user.id,
            profile_id=profile.id,
            credit_score=credit_score,
            risk_category=risk_category,
            repayment_probability=ml_prediction['repayment_probability'],
            features_json=json.dumps({
                'behavioral': behavioral_features,
                'document': doc_features,
                'confidence_level': confidence_level,
                'model_used': ml_prediction.get('model_used', 'XGBoost')
            }),
            document_bonus=0,  # No longer using bonus system
            processed_by=session['employee_id'],
            created_by=session['employee_id'],  # Track who created
            status='draft'  # Start as draft
        )
        db.session.add(assessment)
        db.session.commit()
        
        # Auto-assign to Credit Analyst for review
        success, assigned_to_id, assign_message = assign_assessment_to_analyst(
            assessment.id, 
            loan_officer_id=session['employee_id']
        )
        
        if success:
            db.session.commit()
            flash(f'Assessment completed! Score: {credit_score} ({risk_category}) - {assign_message}', 'success')
        else:
            flash(f'Assessment completed! Score: {credit_score} ({risk_category}) - Note: {assign_message}', 'warning')
        
        return redirect(url_for('bank_assessment_result', id=assessment.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Assessment failed: {str(e)}', 'error')
        return render_template('bank/assessment_form.html')

@app.route('/bank/assessment/<int:id>')
@login_required_bank
def bank_assessment_result(id):
    """Show bank assessment result"""
    assessment = CreditAssessment.query.get_or_404(id)
    
    # Access check - employee can view if:
    # 1. They created it (processed_by or created_by)
    # 2. It's assigned to them
    # 3. They have view_all permission
    employee = Employee.query.get(session.get('employee_id'))
    if employee:
        is_creator = (assessment.processed_by == employee.id or assessment.created_by == employee.id)
        is_assigned = (assessment.assigned_to == employee.id)
        has_view_all = employee.has_permission('view_all') or employee.has_permission('ALL')
        # Managers can view any assessment (needed for pending_approval decisions)
        is_manager = employee.role.lower() in ['branch_manager', 'credit_manager', 'head_of_bank']
        
        if not (is_creator or is_assigned or has_view_all or is_manager):
            abort(403)  # Forbidden, not 404
    
    # Parse features (handle both old and new format)
    raw_features = json.loads(assessment.features_json)
    
    # If new format with behavioral/document keys, flatten it
    if 'behavioral' in raw_features:
        features = {**raw_features['behavioral']}
        features['confidence_level'] = raw_features.get('confidence_level', 0.75)
        features['model_used'] = raw_features.get('model_used', 'XGBoost')
        if 'document' in raw_features:
            features.update(raw_features['document'])
    else:
        # Old format - use as-is
        features = raw_features
    
    # Get analysts for reassign modal (managers only need this)
    employee = Employee.query.get(session.get('employee_id'))
    analysts = []
    if employee and employee.role.lower() in ['branch_manager', 'credit_manager']:
        analysts = Employee.query.filter_by(role='credit_analyst').all()
    
    # Get documents uploaded by the user for this assessment
    # Documents can be linked via user_id OR customer_id (through user's customer relationship)
    documents = DocumentUpload.query.filter_by(user_id=assessment.user_id).all()
    
    # If no documents found by user_id, try finding by customer_id
    if not documents and assessment.user and assessment.user.customer_id:
        documents = DocumentUpload.query.filter_by(customer_id=assessment.user.customer_id).all()
    
    return render_template('bank/result.html', assessment=assessment, features=features, analysts=analysts, documents=documents)


@app.route('/bank/assessment/<int:id>/download_pdf')
@login_required_bank
def bank_assessment_download_pdf(id):
    """Generate and download PDF report - BANK-GRADE VERSION"""
    from bank_grade_pdf_generator import generate_bank_grade_report
    
    assessment = CreditAssessment.query.get_or_404(id)
    user = User.query.get(assessment.user_id) if assessment.user_id else None
    
    if not user:
        flash('User information not found for this assessment', 'error')
        return redirect(url_for('bank_assessment_result', id=id))
    
    try:
        # Generate professional bank-grade PDF
        temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        pdf_path = generate_bank_grade_report(assessment, user, temp_pdf.name)
        
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=f"CreditBridge_Assessment_{assessment.id}.pdf",
            mimetype='application/pdf'
        )
    except Exception as e:
        # Log error in production
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('bank_assessment_result', id=id))


@app.route('/bank/assessment/<int:id>/delete', methods=['POST'])
@login_required_bank
def bank_assessment_delete(id):
    """Delete assessment - Branch Manager only, restricted to own branch"""
    assessment = CreditAssessment.query.get_or_404(id)
    employee = Employee.query.get(session.get('employee_id'))
    
    if not employee:
        abort(403)
    
    # Only Branch Manager can delete
    if employee.role not in ['Branch Manager', 'branch_manager']:
        flash('Only Branch Managers can delete assessments.', 'danger')
        return redirect(url_for('bank_assessment_result', id=id))
    
    # Check if assessment belongs to the manager's branch
    # Assessment's processor or creator should be from the same branch
    assessment_employee = None
    if assessment.processed_by:
        assessment_employee = Employee.query.get(assessment.processed_by)
    elif assessment.created_by:
        assessment_employee = Employee.query.get(assessment.created_by)
    
    if assessment_employee and assessment_employee.branch_id != employee.branch_id:
        flash('You can only delete assessments from your own branch.', 'danger')
        return redirect(url_for('bank_assessment_result', id=id))
    
    # Store info for audit log before deletion
    assessment_info = {
        'id': assessment.id,
        'user_name': assessment.user.name if assessment.user else 'Unknown',
        'credit_score': assessment.credit_score,
        'status': assessment.status
    }
    
    try:
        # Delete related records first
        DocumentUpload.query.filter_by(user_id=assessment.user_id).delete()
        
        # Delete the assessment
        db.session.delete(assessment)
        db.session.commit()
        
        # Log the deletion
        AuditLog.log(
            employee_id=employee.id,
            action='ASSESSMENT_DELETED',
            entity_type='assessment',
            entity_id=assessment_info['id'],
            before=json.dumps(assessment_info),
            after=None,
            details=f"Assessment #{assessment_info['id']} for {assessment_info['user_name']} deleted by {employee.full_name}",
            ip=request.remote_addr
        )
        
        flash(f'Assessment #{assessment_info["id"]} has been deleted successfully.', 'success')
        return redirect(url_for('bank_applications'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting assessment: {str(e)}', 'danger')
        return redirect(url_for('bank_assessment_result', id=id))


@app.route('/bank/applications')
@login_required_bank
def bank_applications():
    """List bank applications - filtered by role and branch"""
    employee = Employee.query.get(session['employee_id'])
    if not employee:
        flash('Session expired. Please login again.', 'error')
        return redirect(url_for('bank_login'))
    
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Get branch filter from query params (for admin/credit_manager)
    branch_filter = request.args.get('branch', type=int)
    
    # Get all branches for dropdown (only for admin/credit_manager)
    branches = []
    if employee.role in ['head_of_bank', 'credit_manager']:
        branches = Branch.query.filter_by(status='active').all()
    
    # Use role-based filtering
    applications = get_accessible_assessments(employee, branch_filter).filter(
        CreditAssessment.created_by.isnot(None)
    ).order_by(CreditAssessment.assessment_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('bank/applications.html', 
                           applications=applications, 
                           branches=branches,
                           selected_branch=branch_filter,
                           employee=employee)

@app.route('/bank/customers')
@login_required_bank
def bank_customers():
    """List bank customers - filtered by role and branch"""
    employee = Employee.query.get(session['employee_id'])
    if not employee:
        flash('Session expired. Please login again.', 'error')
        return redirect(url_for('bank_login'))
    
    page = request.args.get('page', 1, type=int)
    per_page = 20
    branch_filter = request.args.get('branch', type=int)
    
    # Get branches for dropdown (admin/credit only)
    branches = []
    if employee.role in ['head_of_bank', 'credit_manager']:
        branches = Branch.query.filter_by(status='active').all()
    
    # Get accessible assessments to find related customers
    accessible = get_accessible_assessments(employee, branch_filter)
    user_ids = [a.user_id for a in accessible.all()]
    
    if user_ids:
        customers = User.query.filter(
            User.id.in_(user_ids)
        ).order_by(User.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
    else:
        customers = User.query.filter_by(id=None).paginate(
            page=page, per_page=per_page, error_out=False
        )
    
    return render_template('bank/customers.html', 
                           customers=customers,
                           branches=branches,
                           selected_branch=branch_filter,
                           employee=employee)

@app.route('/bank/analytics')
@login_required_bank
def bank_analytics():
    """
    Comprehensive analytics dashboard with role-based filtering.
    
    Data access by role:
    - head_of_bank: All branches, all assessments
    - branch_manager: Own branch assessments only
    - credit_manager: Own team assessments only
    - loan_officer: Own created assessments only
    - credit_analyst: Assigned assessments only
    """
    from sqlalchemy import func, case
    import json
    
    employee = Employee.query.get(session['employee_id'])
    if not employee:
        flash('Session expired. Please login again.', 'error')
        return redirect(url_for('bank_login'))
    
    # ─── Date Range Handling ────────────────────────────────────────────────────
    end_date_str = request.args.get('end_date')
    start_date_str = request.args.get('start_date')
    
    # Default: last 30 days
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)
    
    # Parse provided dates with validation
    try:
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            end_date = end_date.replace(hour=23, minute=59, second=59)
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            start_date = start_date.replace(hour=0, minute=0, second=0)
        
        # Validate: start <= end
        if start_date > end_date:
            start_date, end_date = end_date, start_date
        
        # Limit to 1 year max
        if (end_date - start_date).days > 365:
            start_date = end_date - timedelta(days=365)
    except ValueError:
        # Invalid date format, use defaults
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
    
    # ─── Get Role-Based Accessible Assessments ──────────────────────────────────
    base_query = get_accessible_assessments(employee)
    
    # Apply date filter
    filtered_query = base_query.filter(
        CreditAssessment.assessment_date.between(start_date, end_date)
    )
    
    # ─── Calculate KPIs ─────────────────────────────────────────────────────────
    total_assessments = filtered_query.count()
    
    # Status counts
    approved_count = filtered_query.filter(CreditAssessment.status == 'approved').count()
    rejected_count = filtered_query.filter(CreditAssessment.status == 'rejected').count()
    pending_count = filtered_query.filter(
        CreditAssessment.status.in_(['draft', 'pending_review', 'under_review', 'reviewed', 'pending_approval'])
    ).count()
    
    approval_rate = round((approved_count / total_assessments * 100), 1) if total_assessments > 0 else 0
    
    # Average credit score
    avg_score_result = db.session.query(func.avg(CreditAssessment.credit_score)).filter(
        CreditAssessment.id.in_(filtered_query.with_entities(CreditAssessment.id).subquery())
    ).scalar()
    avg_credit_score = round(avg_score_result, 0) if avg_score_result else 0
    
    # Average processing time
    avg_time_result = db.session.query(func.avg(CreditAssessment.processing_time_minutes)).filter(
        CreditAssessment.id.in_(filtered_query.with_entities(CreditAssessment.id).subquery()),
        CreditAssessment.processing_time_minutes.isnot(None)
    ).scalar()
    avg_processing_time = round(avg_time_result, 0) if avg_time_result else 0
    
    # ─── Calculate Trends (compare with previous period) ───────────────────────
    period_length = (end_date - start_date).days
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=period_length)
    
    prev_query = base_query.filter(
        CreditAssessment.assessment_date.between(prev_start, prev_end)
    )
    prev_total = prev_query.count()
    prev_approved = prev_query.filter(CreditAssessment.status == 'approved').count()
    prev_approval_rate = round((prev_approved / prev_total * 100), 1) if prev_total > 0 else 0
    
    prev_avg_score = db.session.query(func.avg(CreditAssessment.credit_score)).filter(
        CreditAssessment.id.in_(prev_query.with_entities(CreditAssessment.id).subquery())
    ).scalar() or 0
    
    prev_avg_time = db.session.query(func.avg(CreditAssessment.processing_time_minutes)).filter(
        CreditAssessment.id.in_(prev_query.with_entities(CreditAssessment.id).subquery()),
        CreditAssessment.processing_time_minutes.isnot(None)
    ).scalar() or 0
    
    # Trend calculations
    total_trend = round(((total_assessments - prev_total) / prev_total * 100), 1) if prev_total > 0 else 0
    approval_trend = round(approval_rate - prev_approval_rate, 1)
    score_trend = round(avg_credit_score - prev_avg_score, 0)
    time_trend = round(prev_avg_time - avg_processing_time, 0)  # Negative is better for time
    
    kpis = {
        'total_assessments': total_assessments,
        'total_trend': total_trend,
        'approval_rate': approval_rate,
        'approval_trend': approval_trend,
        'avg_credit_score': avg_credit_score,
        'score_trend': score_trend,
        'avg_processing_time': avg_processing_time,
        'time_trend': time_trend,
        'approved': approved_count,
        'rejected': rejected_count,
        'pending': pending_count
    }
    
    # ─── Risk Distribution ──────────────────────────────────────────────────────
    risk_distribution_raw = db.session.query(
        CreditAssessment.risk_category,
        func.count(CreditAssessment.id)
    ).filter(
        CreditAssessment.id.in_(filtered_query.with_entities(CreditAssessment.id).subquery())
    ).group_by(CreditAssessment.risk_category).all()
    
    # Convert to list of dicts for JSON serialization
    risk_distribution = [{'category': r[0] or 'Unknown', 'count': r[1]} for r in risk_distribution_raw]
    
    # ─── Weekly Trends (last 12 weeks) ──────────────────────────────────────────
    weekly_trends = []
    for i in range(12, 0, -1):
        week_end = end_date - timedelta(weeks=i-1)
        week_start = week_end - timedelta(days=7)
        
        week_count = base_query.filter(
            CreditAssessment.assessment_date.between(week_start, week_end)
        ).count()
        
        weekly_trends.append({
            'week': f'Week {13-i}',
            'count': week_count,
            'label': week_start.strftime('%d %b')
        })
    
    # ─── Score Distribution (Histogram) ─────────────────────────────────────────
    score_ranges = [
        (300, 400, '300-400'),
        (400, 500, '400-500'),
        (500, 550, '500-550'),
        (550, 600, '550-600'),
        (600, 650, '600-650'),
        (650, 700, '650-700'),
        (700, 750, '700-750'),
        (750, 800, '750-800'),
        (800, 900, '800-900')
    ]
    
    score_distribution = []
    for min_score, max_score, label in score_ranges:
        count = filtered_query.filter(
            CreditAssessment.credit_score >= min_score,
            CreditAssessment.credit_score < max_score
        ).count()
        score_distribution.append({'range': label, 'count': count})
    
    # ─── Approval Rate by Risk Category ─────────────────────────────────────────
    approval_by_risk = []
    for risk_cat in ['Low Risk', 'Medium Risk', 'High Risk']:
        risk_query = filtered_query.filter(CreditAssessment.risk_category == risk_cat)
        risk_total = risk_query.count()
        risk_approved = risk_query.filter(CreditAssessment.status == 'approved').count()
        risk_rejected = risk_query.filter(CreditAssessment.status == 'rejected').count()
        
        approval_by_risk.append({
            'category': risk_cat,
            'total': risk_total,
            'approved': risk_approved,
            'rejected': risk_rejected,
            'approval_rate': round((risk_approved / risk_total * 100), 1) if risk_total > 0 else 0
        })
    
    # ─── Behavioral Metrics Averages ────────────────────────────────────────────
    behavioral_metrics = {
        'income_stability': 0,
        'expense_control': 0,
        'payment_consistency': 0,
        'digital_activity': 0,
        'savings_discipline': 0,
        'cashflow_health': 0
    }
    
    # Get assessments with features
    assessments_with_features = filtered_query.filter(
        CreditAssessment.features_json.isnot(None)
    ).limit(100).all()  # Limit for performance
    
    if assessments_with_features:
        metric_sums = {k: 0 for k in behavioral_metrics.keys()}
        valid_count = 0
        
        for assessment in assessments_with_features:
            try:
                features = json.loads(assessment.features_json)
                if features:
                    valid_count += 1
                    metric_sums['income_stability'] += features.get('income_stability_index', 0)
                    metric_sums['expense_control'] += features.get('expense_control_ratio', 0)
                    metric_sums['payment_consistency'] += features.get('payment_consistency_score', 0)
                    metric_sums['digital_activity'] += features.get('digital_activity_score', 0)
                    metric_sums['savings_discipline'] += features.get('savings_discipline_ratio', 0)
                    metric_sums['cashflow_health'] += features.get('cashflow_health_score', 
                                                                   features.get('cashflow_ratio', 0))
            except (json.JSONDecodeError, TypeError):
                continue
        
        if valid_count > 0:
            for key in behavioral_metrics:
                behavioral_metrics[key] = round((metric_sums[key] / valid_count) * 100, 1)
    
    # ─── Branch Performance (for head_of_bank and branch_manager) ───────────────
    branch_performance = []
    if employee.role in ['head_of_bank', 'branch_manager']:
        if employee.role == 'head_of_bank':
            branches = Branch.query.filter_by(status='active').all()
        else:
            branches = [Branch.query.get(employee.branch_id)] if employee.branch_id else []
        
        for branch in branches:
            if not branch:
                continue
            branch_query = CreditAssessment.query.filter(
                CreditAssessment.assessment_date.between(start_date, end_date)
            )
            # Filter by branch - need to join through Employee
            branch_employees = Employee.query.filter_by(branch_id=branch.id).all()
            branch_emp_ids = [e.id for e in branch_employees]
            
            if branch_emp_ids:
                from sqlalchemy import or_
                branch_assessments = branch_query.filter(
                    or_(
                        CreditAssessment.created_by.in_(branch_emp_ids),
                        CreditAssessment.assigned_to.in_(branch_emp_ids)
                    )
                )
                
                b_total = branch_assessments.count()
                if b_total > 0:
                    b_approved = branch_assessments.filter(CreditAssessment.status == 'approved').count()
                    b_avg_score = db.session.query(func.avg(CreditAssessment.credit_score)).filter(
                        CreditAssessment.id.in_(branch_assessments.with_entities(CreditAssessment.id).subquery())
                    ).scalar() or 0
                    
                    branch_performance.append({
                        'name': branch.branch_name,
                        'code': branch.branch_code,
                        'assessments': b_total,
                        'approval_rate': round((b_approved / b_total * 100), 1),
                        'avg_score': round(b_avg_score, 0)
                    })
    
    # ─── Top Performing Employees (for managers) ────────────────────────────────
    top_employees = []
    if employee.role in ['branch_manager', 'credit_manager']:
        if employee.role == 'branch_manager':
            team_members = Employee.query.filter_by(
                branch_id=employee.branch_id,
                status='ACTIVE'
            ).all()
        else:
            team_members = Employee.query.filter_by(
                team_id=employee.team_id,
                status='ACTIVE'
            ).all() if employee.team_id else []
        
        for member in team_members:
            # Count assessments they created or were assigned
            member_query = filtered_query.filter(
                (CreditAssessment.created_by == member.id) | 
                (CreditAssessment.assigned_to == member.id)
            )
            m_total = member_query.count()
            
            if m_total > 0:
                m_approved = member_query.filter(CreditAssessment.status == 'approved').count()
                m_avg_time = db.session.query(func.avg(CreditAssessment.processing_time_minutes)).filter(
                    CreditAssessment.id.in_(member_query.with_entities(CreditAssessment.id).subquery()),
                    CreditAssessment.processing_time_minutes.isnot(None)
                ).scalar() or 0
                
                top_employees.append({
                    'name': member.full_name,
                    'role': member.role.replace('_', ' ').title(),
                    'assessments': m_total,
                    'approval_rate': round((m_approved / m_total * 100), 1),
                    'avg_time': round(m_avg_time, 0)
                })
        
        # Sort by approval rate descending
        top_employees.sort(key=lambda x: x['approval_rate'], reverse=True)
        top_employees = top_employees[:10]  # Top 10
    
    # ─── Recent Assessments ─────────────────────────────────────────────────────
    recent_assessments = filtered_query.order_by(
        CreditAssessment.assessment_date.desc()
    ).limit(10).all()
    
    # ─── Package All Analytics Data ─────────────────────────────────────────────
    analytics_data = {
        'kpis': kpis,
        'risk_distribution': risk_distribution,
        'weekly_trends': weekly_trends,
        'score_distribution': score_distribution,
        'approval_by_risk': approval_by_risk,
        'behavioral_metrics': behavioral_metrics,
        'branch_performance': branch_performance,
        'top_employees': top_employees,
        'recent_assessments': recent_assessments,
        'date_range': {
            'start': start_date.strftime('%Y-%m-%d'),
            'end': end_date.strftime('%Y-%m-%d')
        }
    }
    
    return render_template('bank/analytics.html', 
                         analytics=analytics_data,
                         employee=employee)
# ============================================================================
# ANALYTICS EXPORT ROUTE
# ============================================================================

@app.route('/bank/analytics/export')
@login_required_bank
def export_analytics():
    """
    Export analytics data as CSV.
    Uses same role-based filtering as main analytics page.
    """
    import csv
    import io
    
    employee = Employee.query.get(session['employee_id'])
    if not employee:
        flash('Session expired. Please login again.', 'error')
        return redirect(url_for('bank_login'))
    
    format_type = request.args.get('format', 'csv')
    
    # Parse date range
    end_date_str = request.args.get('end_date')
    start_date_str = request.args.get('start_date')
    
    # Default: last 30 days
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)
    
    try:
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            end_date = end_date.replace(hour=23, minute=59, second=59)
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            start_date = start_date.replace(hour=0, minute=0, second=0)
    except ValueError:
        pass
    
    # Get role-based filtered assessments
    base_query = get_accessible_assessments(employee)
    assessments = base_query.filter(
        CreditAssessment.assessment_date.between(start_date, end_date)
    ).order_by(CreditAssessment.assessment_date.desc()).all()
    
    if format_type == 'csv':
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header row
        writer.writerow([
            'ID', 'Applicant Name', 'Credit Score', 'Risk Category',
            'Repayment Probability', 'Status', 'Created Date',
            'Created By', 'Assigned To'
        ])
        
        # Data rows
        for a in assessments:
            applicant_name = a.user.name if a.user else 'N/A'
            created_by = Employee.query.get(a.created_by).full_name if a.created_by else 'Public Portal'
            assigned_to = Employee.query.get(a.assigned_to).full_name if a.assigned_to else 'Unassigned'
            
            writer.writerow([
                a.id,
                applicant_name,
                a.credit_score,
                a.risk_category,
                f"{a.repayment_probability:.2%}" if a.repayment_probability else 'N/A',
                a.status,
                a.assessment_date.strftime('%Y-%m-%d %H:%M') if a.assessment_date else 'N/A',
                created_by,
                assigned_to
            ])
        
        # Create response
        from flask import make_response
        response = make_response(output.getvalue())
        filename = f'analytics_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        response.headers['Content-Type'] = 'text/csv'
        return response
    
    # Default: redirect back with error
    flash('Export format not supported', 'error')
    return redirect(url_for('bank_analytics'))


# ============================================================================
# ROLE-SPECIFIC ROUTES
# ============================================================================

@app.route('/bank/team-management')
@login_required_bank
@permission_required('MANAGE_USERS', 'ALL')
def bank_team_management():
    """Team management for Branch Manager"""
    employees = Employee.query.order_by(Employee.role, Employee.full_name).all()
    
    # Calculate stats for each employee
    employee_stats = []
    for emp in employees:
        assessments_count = CreditAssessment.query.filter(
            (CreditAssessment.created_by == emp.id) | (CreditAssessment.assigned_to == emp.id)
        ).count()
        pending_count = CreditAssessment.query.filter(
            (CreditAssessment.assigned_to == emp.id) & 
            CreditAssessment.status.in_(['pending_review', 'under_review'])
        ).count()
        
        employee_stats.append({
            'employee': emp,
            'assessments_count': assessments_count,
            'pending_count': pending_count
        })
    
    return render_template('bank/team_management.html', employee_stats=employee_stats)


@app.route('/bank/audit-logs')
@login_required_bank
@permission_required('VIEW_AUDIT_LOGS', 'ALL')
def bank_audit_logs():
    """View audit logs for Branch Manager"""
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('bank/audit_logs.html', logs=logs)


@app.route('/bank/escalations')
@login_required_bank
@permission_required('VIEW_ESCALATIONS', 'ALL')
def bank_escalations():
    """View escalated assessments for Credit Manager"""
    escalated = CreditAssessment.query.filter_by(status='escalated').order_by(
        CreditAssessment.assessment_date.desc()
    ).all()
    
    return render_template('bank/escalations.html', escalations=escalated)


@app.route('/bank/assigned-queue')
@login_required_bank
def bank_assigned_queue():
    """View assigned assessments for Credit Analyst"""
    employee = Employee.query.get(session['employee_id'])
    
    # Get assessments assigned to this analyst
    pending = CreditAssessment.query.filter(
        CreditAssessment.assigned_to == employee.id,
        CreditAssessment.status.in_(['pending_review', 'under_review'])
    ).order_by(CreditAssessment.priority.desc(), CreditAssessment.assessment_date.asc()).all()
    
    # Get completed reviews
    completed = CreditAssessment.query.filter(
        CreditAssessment.reviewed_by == employee.id
    ).order_by(CreditAssessment.reviewed_at.desc()).limit(10).all()
    
    return render_template('bank/assigned_queue.html', pending=pending, completed=completed, employee=employee)


# ============================================================================
# WORKFLOW ACTION ROUTES
# ============================================================================

@app.route('/bank/assessment/<int:id>/approve', methods=['POST'])
@login_required_bank
@permission_required('APPROVE_ASSESSMENTS')
def bank_assessment_approve(id):
    """Approve an assessment - Branch Manager or Credit Manager"""
    assessment = CreditAssessment.query.get_or_404(id)
    employee = Employee.query.get(session['employee_id'])
    notes = request.form.get('notes', '')
    
    # Store old status for audit
    old_status = assessment.status
    
    # Validate the transition
    if assessment.status not in ['reviewed', 'pending_approval']:
        flash(f'Cannot approve assessment in "{assessment.status}" status.', 'error')
        return redirect(url_for('bank_assessment_result', id=id))
    
    # Update assessment
    assessment.status = 'approved'
    assessment.approved_by = employee.id
    assessment.approved_at = datetime.utcnow()
    assessment.override_notes = notes
    assessment.previous_status = old_status
    
    # Create audit log
    AuditLog.log(
        employee_id=employee.id,
        action='APPROVE',
        entity_type='assessment',
        entity_id=id,
        before=old_status,
        after='approved',
        details={'action': 'Assessment approved', 'credit_score': assessment.credit_score, 'notes': notes},
        ip=request.remote_addr,
        user_agent=request.headers.get('User-Agent', '')
    )
    
    # Create notification for creator
    if assessment.created_by:
        Notification.create(
            employee_id=assessment.created_by,
            assessment_id=id,
            notification_type='APPROVED',
            message=f'Assessment #{id} has been approved by {employee.full_name}',
            priority='MEDIUM'
        )
    
    db.session.commit()
    flash(f'Assessment #{id} approved successfully!', 'success')
    return redirect(url_for('bank_assessment_result', id=id))


@app.route('/bank/assessment/<int:id>/reject', methods=['POST'])
@login_required_bank
@permission_required('REJECT_ASSESSMENTS')
def bank_assessment_reject(id):
    """Reject an assessment"""
    assessment = CreditAssessment.query.get_or_404(id)
    employee = Employee.query.get(session['employee_id'])
    reason = request.form.get('reason', 'No reason provided')
    
    old_status = assessment.status
    
    if assessment.status not in ['reviewed', 'pending_approval', 'under_review']:
        flash(f'Cannot reject assessment in "{assessment.status}" status.', 'error')
        return redirect(url_for('bank_assessment_result', id=id))
    
    assessment.status = 'rejected'
    assessment.approved_by = employee.id
    assessment.approved_at = datetime.utcnow()
    assessment.rejection_reason = reason
    assessment.previous_status = old_status
    
    AuditLog.log(
        employee_id=employee.id,
        action='REJECT',
        entity_type='assessment',
        entity_id=id,
        before=old_status,
        after='rejected',
        details={'reason': reason, 'credit_score': assessment.credit_score},
        ip=request.remote_addr,
        user_agent=request.headers.get('User-Agent', '')
    )
    
    if assessment.created_by:
        Notification.create(
            employee_id=assessment.created_by,
            assessment_id=id,
            notification_type='REJECTED',
            message=f'Assessment #{id} was rejected: {reason}',
            priority='HIGH'
        )
    
    db.session.commit()
    flash(f'Assessment #{id} rejected.', 'warning')
    return redirect(url_for('bank_assessment_result', id=id))


@app.route('/bank/assessment/<int:id>/escalate', methods=['POST'])
@login_required_bank
def bank_assessment_escalate(id):
    """Escalate an assessment to manager"""
    assessment = CreditAssessment.query.get_or_404(id)
    employee = Employee.query.get(session['employee_id'])
    reason = request.form.get('reason', 'Requires manager attention')
    
    old_status = assessment.status
    
    if assessment.status == 'escalated':
        flash('Assessment is already escalated.', 'warning')
        return redirect(url_for('bank_assessment_result', id=id))
    
    assessment.status = 'escalated'
    assessment.escalation_reason = reason
    assessment.previous_status = old_status
    
    AuditLog.log(
        employee_id=employee.id,
        action='UPDATE',
        entity_type='assessment',
        entity_id=id,
        before=old_status,
        after='escalated',
        details={'escalation_reason': reason},
        ip=request.remote_addr,
        user_agent=request.headers.get('User-Agent', '')
    )
    
    # Notify managers
    managers = Employee.query.filter(Employee.role.in_(['Branch Manager', 'Credit Manager'])).all()
    for manager in managers:
        Notification.create(
            employee_id=manager.id,
            assessment_id=id,
            notification_type='ESCALATION',
            message=f'Assessment #{id} escalated by {employee.full_name}: {reason}',
            priority='URGENT'
        )
    
    db.session.commit()
    flash(f'Assessment #{id} escalated to management.', 'info')
    return redirect(url_for('bank_assessment_result', id=id))


@app.route('/bank/assessment/<int:id>/submit-for-review', methods=['POST'])
@login_required_bank
def bank_assessment_submit_review(id):
    """Submit assessment for review (Loan Officer -> Credit Analyst)"""
    assessment = CreditAssessment.query.get_or_404(id)
    employee = Employee.query.get(session['employee_id'])
    
    old_status = assessment.status
    
    # Can only submit drafts
    if assessment.status != 'draft':
        flash(f'Cannot submit assessment in "{assessment.status}" status.', 'error')
        return redirect(url_for('bank_assessment_result', id=id))
    
    # Must be the creator
    if assessment.created_by != employee.id:
        flash('You can only submit your own assessments.', 'error')
        return redirect(url_for('bank_assessment_result', id=id))
    
    assessment.status = 'pending_review'
    assessment.submitted_at = datetime.utcnow()
    assessment.previous_status = old_status
    
    # Auto-assign to credit analyst
    result = assign_assessment_to_analyst(id, employee.id)
    
    AuditLog.log(
        employee_id=employee.id,
        action='UPDATE',
        entity_type='assessment',
        entity_id=id,
        before=old_status,
        after='pending_review',
        details={'action': 'Submitted for review', 'assignment': result},
        ip=request.remote_addr,
        user_agent=request.headers.get('User-Agent', '')
    )
    
    db.session.commit()
    flash(f'Assessment #{id} submitted for review.', 'success')
    return redirect(url_for('bank_assessment_result', id=id))


@app.route('/bank/assessment/<int:id>/complete-review', methods=['POST'])
@login_required_bank
def bank_assessment_complete_review(id):
    """Complete review and submit for approval (Credit Analyst)"""
    assessment = CreditAssessment.query.get_or_404(id)
    employee = Employee.query.get(session['employee_id'])
    notes = request.form.get('notes', '')
    recommendation = request.form.get('recommendation', 'approve')
    
    old_status = assessment.status
    
    if assessment.status not in ['pending_review', 'under_review']:
        flash(f'Cannot complete review for assessment in "{assessment.status}" status.', 'error')
        return redirect(url_for('bank_assessment_result', id=id))
    
    # Must be assigned to this analyst
    if assessment.assigned_to != employee.id:
        flash('This assessment is not assigned to you.', 'error')
        return redirect(url_for('bank_assessment_result', id=id))
    
    assessment.status = 'pending_approval'
    assessment.reviewed_by = employee.id
    assessment.reviewed_at = datetime.utcnow()
    assessment.review_notes = notes
    assessment.previous_status = old_status
    
    # Calculate processing time
    if assessment.submitted_at:
        delta = datetime.utcnow() - assessment.submitted_at
        assessment.processing_time_minutes = int(delta.total_seconds() / 60)
    
    AuditLog.log(
        employee_id=employee.id,
        action='UPDATE',
        entity_type='assessment',
        entity_id=id,
        before={'status': old_status},
        after={'status': 'pending_approval'},
        details={'action': 'Review completed', 'notes': notes},
        ip=request.remote_addr,
        user_agent=request.headers.get('User-Agent', '')
    )
    
    # Notify creator and managers
    if assessment.created_by:
        Notification.create(
            employee_id=assessment.created_by,
            assessment_id=id,
            notification_type='REVIEWED',
            message=f'Assessment #{id} reviewed and pending approval',
            priority='MEDIUM'
        )
    
    managers = Employee.query.filter(Employee.role.in_(['branch_manager', 'credit_manager', 'head_of_bank'])).all()
    for manager in managers:
        Notification.create(
            employee_id=manager.id,
            assessment_id=id,
            notification_type='REVIEWED',
            message=f'Assessment #{id} recommendation: {recommendation.upper()} by {employee.full_name}',
            priority='MEDIUM'
        )
    
    db.session.commit()
    flash(f'Recommendation for assessment #{id} submitted to Manager.', 'success')
    return redirect(url_for('bank_assessment_result', id=id))


@app.route('/bank/assessment/<int:id>/start-review', methods=['POST'])
@login_required_bank
def bank_assessment_start_review(id):
    """Start reviewing an assessment (Credit Analyst)"""
    assessment = CreditAssessment.query.get_or_404(id)
    employee = Employee.query.get(session['employee_id'])
    
    old_status = assessment.status
    
    if assessment.status != 'pending_review':
        flash(f'Cannot start review for assessment in "{assessment.status}" status.', 'error')
        return redirect(url_for('bank_assessment_result', id=id))
    
    # Must be assigned to this analyst
    if assessment.assigned_to != employee.id:
        flash('This assessment is not assigned to you.', 'error')
        return redirect(url_for('bank_assessment_result', id=id))
    
    assessment.status = 'under_review'
    assessment.previous_status = old_status
    
    AuditLog.log(
        employee_id=employee.id,
        action='UPDATE',
        entity_type='assessment',
        entity_id=id,
        before=old_status,
        after='under_review',
        details={'action': 'Started review'},
        ip=request.remote_addr,
        user_agent=request.headers.get('User-Agent', '')
    )
    
    db.session.commit()
    flash(f'Started reviewing assessment #{id}.', 'info')
    return redirect(url_for('bank_assessment_result', id=id))


@app.route('/bank/assessment/<int:id>/reassign', methods=['POST'])
@login_required_bank
@permission_required('REASSIGN', 'MANAGE_USERS')
def bank_assessment_reassign(id):
    """Reassign assessment to different analyst"""
    assessment = CreditAssessment.query.get_or_404(id)
    employee = Employee.query.get(session['employee_id'])
    new_analyst_id = request.form.get('analyst_id', type=int)
    reason = request.form.get('reason', 'Reassigned by manager')
    
    if not new_analyst_id:
        flash('Please select an analyst to reassign to.', 'error')
        return redirect(url_for('bank_assessment_result', id=id))
    
    new_analyst = Employee.query.get(new_analyst_id)
    if not new_analyst:
        flash('Selected analyst not found.', 'error')
        return redirect(url_for('bank_assessment_result', id=id))
    
    old_analyst_id = assessment.assigned_to
    
    # Create assignment history
    history = AssignmentHistory(
        assessment_id=id,
        assigned_from=old_analyst_id,
        assigned_to=new_analyst_id,
        assignment_type='REASSIGN',
        reason=reason
    )
    db.session.add(history)
    
    assessment.assigned_to = new_analyst_id
    if assessment.status == 'under_review':
        assessment.status = 'pending_review'  # Reset to pending
    
    AuditLog.log(
        employee_id=employee.id,
        action='REASSIGN',
        entity_type='assessment',
        entity_id=id,
        before=str(old_analyst_id),
        after=str(new_analyst_id),
        details={'reason': reason, 'new_analyst': new_analyst.full_name},
        ip=request.remote_addr,
        user_agent=request.headers.get('User-Agent', '')
    )
    
    # Notify new analyst
    Notification.create(
        employee_id=new_analyst_id,
        assessment_id=id,
        notification_type='ASSIGNMENT',
        message=f'Assessment #{id} assigned to you: {reason}',
        priority='HIGH'
    )
    
    db.session.commit()
    flash(f'Assessment #{id} reassigned to {new_analyst.full_name}.', 'success')
    return redirect(url_for('bank_assessment_result', id=id))


@app.route('/bank/assessment/<int:id>/override', methods=['POST'])
@login_required_bank
@permission_required('OVERRIDE')
def bank_assessment_override(id):
    """Override assessment decision - Branch Manager only"""
    assessment = CreditAssessment.query.get_or_404(id)
    employee = Employee.query.get(session['employee_id'])
    new_status = request.form.get('status')
    notes = request.form.get('notes', 'Manager override')
    
    if new_status not in ['approved', 'rejected']:
        flash('Invalid override status.', 'error')
        return redirect(url_for('bank_assessment_result', id=id))
    
    old_status = assessment.status
    
    assessment.status = new_status
    assessment.override_notes = notes
    assessment.approved_by = employee.id
    assessment.approved_at = datetime.utcnow()
    assessment.previous_status = old_status
    
    AuditLog.log(
        employee_id=employee.id,
        action='OVERRIDE',
        entity_type='assessment',
        entity_id=id,
        before=old_status,
        after=new_status,
        details={'override_notes': notes, 'action': f'Manager override to {new_status}'},
        ip=request.remote_addr,
        user_agent=request.headers.get('User-Agent', '')
    )
    
    if assessment.created_by:
        Notification.create(
            employee_id=assessment.created_by,
            assessment_id=id,
            notification_type='OVERRIDE',
            message=f'Assessment #{id} overridden to {new_status} by {employee.full_name}',
            priority='URGENT'
        )
    
    db.session.commit()
    flash(f'Assessment #{id} overridden to {new_status}.', 'warning')
    return redirect(url_for('bank_assessment_result', id=id))

@app.route('/bank/download-report/<int:id>')
@login_required_bank
def bank_download_report(id):
    """Download bank assessment PDF report - BANK-GRADE VERSION"""
    from bank_grade_pdf_generator import generate_bank_grade_report
    
    assessment = CreditAssessment.query.get_or_404(id)
    
    # Verify this is a bank assessment
    if assessment.processed_by is None:
        abort(404)
    
    user = User.query.get(assessment.user_id) if assessment.user_id else None
    
    if not user:
        flash('User information not found for this assessment', 'error')
        return redirect(url_for('bank_assessment_result', id=id))
    
    try:
        # Generate professional bank-grade PDF
        temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        pdf_path = generate_bank_grade_report(assessment, user, temp_pdf.name)
        
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=f'bank_assessment_{assessment.id}.pdf',
            mimetype='application/pdf'
        )
        
    except Exception as e:
        flash(f'Report generation failed: {str(e)}', 'error')
        return redirect(url_for('bank_assessment_result', id=id))

# API Routes
@app.route('/api/analytics')
@login_required_bank
@permission_required('analytics')
def api_analytics():
    """Analytics API for charts"""
    # Monthly assessment counts
    monthly_data = []
    for i in range(12):
        month_start = datetime.utcnow().replace(day=1) - timedelta(days=30*i)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        count = CreditAssessment.query.filter(
            CreditAssessment.processed_by.isnot(None),
            CreditAssessment.assessment_date >= month_start,
            CreditAssessment.assessment_date <= month_end
        ).count()
        
        monthly_data.append({
            'month': month_start.strftime('%Y-%m'),
            'count': count
        })
    
    return jsonify({
        'monthly_assessments': monthly_data[::-1]  # Reverse for chronological order
    })

@app.route('/api/assessment/<int:id>', methods=['DELETE'])
@login_required_bank
@permission_required('ALL')  # Only Branch Manager
def api_delete_assessment(id):
    """Delete assessment (Branch Manager only)"""
    assessment = CreditAssessment.query.get_or_404(id)
    
    # Verify this is a bank assessment
    if assessment.processed_by is None:
        abort(404)
    
    try:
        db.session.delete(assessment)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# Helper functions
def seed_branches():
    """Seed demo branches if none exist"""
    if Branch.query.count() > 0:
        return
    
    branches = [
        {
            'branch_code': 'BR001',
            'branch_name': 'Downtown Main Branch',
            'address': '123 Main Street',
            'city': 'Mumbai',
            'state': 'Maharashtra',
            'pincode': '400001',
            'phone': '+91 22 1234 5678',
            'email': 'downtown@creditbridge.com',
            'monthly_target': 200,
            'daily_target': 10
        },
        {
            'branch_code': 'BR002',
            'branch_name': 'Andheri West Branch',
            'address': '456 Link Road',
            'city': 'Mumbai',
            'state': 'Maharashtra',
            'pincode': '400058',
            'phone': '+91 22 2345 6789',
            'email': 'andheri@creditbridge.com',
            'monthly_target': 150,
            'daily_target': 8
        },
        {
            'branch_code': 'BR003',
            'branch_name': 'Pune Central Branch',
            'address': '789 FC Road',
            'city': 'Pune',
            'state': 'Maharashtra',
            'pincode': '411001',
            'phone': '+91 20 3456 7890',
            'email': 'pune@creditbridge.com',
            'monthly_target': 120,
            'daily_target': 6
        }
    ]
    
    for branch_data in branches:
        branch = Branch(**branch_data)
        db.session.add(branch)
    
    db.session.commit()
    print("✓ Seeded 3 demo branches")


def seed_employees():
    """Seed demo employees with 5-role hierarchy across branches"""
    if Employee.query.count() > 0:
        return
    
    # Ensure branches exist first
    seed_branches()
    
    # Get branch IDs
    downtown = Branch.query.filter_by(branch_code='BR001').first()
    andheri = Branch.query.filter_by(branch_code='BR002').first()
    pune = Branch.query.filter_by(branch_code='BR003').first()
    
    downtown_id = downtown.id if downtown else None
    andheri_id = andheri.id if andheri else None
    pune_id = pune.id if pune else None
    
    # Employee data with 5-role hierarchy - SIMPLE CREDENTIALS for demo
    employees = [
        # HEAD OF BANK - Super Admin (no branch - sees all)
        {
            'username': 'admin',
            'password': 'pass123',
            'full_name': 'Rajesh Kumar',
            'email': 'admin@creditbridge.in',
            'employee_code': 'HOB001',
            'role': 'head_of_bank',
            'branch_id': None,
            'team_id': None,
            'manager_id': None,
            'department': 'executive',
            'permissions': json.dumps(ROLE_PERMISSIONS['head_of_bank'])
        },
        
        # BRANCH MANAGERS - One per branch
        {
            'username': 'manager1',
            'password': 'pass123',
            'full_name': 'Sunita Patel',
            'email': 'manager1@creditbridge.in',
            'employee_code': 'BM001',
            'role': 'branch_manager',
            'branch_id': downtown_id,
            'team_id': 'branch_downtown',
            'manager_id': None,
            'department': 'retail_banking',
            'permissions': json.dumps(ROLE_PERMISSIONS['branch_manager'])
        },
        {
            'username': 'manager2',
            'password': 'pass123',
            'full_name': 'Amit Deshmukh',
            'email': 'manager2@creditbridge.in',
            'employee_code': 'BM002',
            'role': 'branch_manager',
            'branch_id': andheri_id,
            'team_id': 'branch_andheri',
            'manager_id': None,
            'department': 'retail_banking',
            'permissions': json.dumps(ROLE_PERMISSIONS['branch_manager'])
        },
        
        # CREDIT MANAGER - One for all branches
        {
            'username': 'credit',
            'password': 'pass123',
            'full_name': 'Priya Sharma',
            'email': 'credit@creditbridge.in',
            'employee_code': 'CM001',
            'role': 'credit_manager',
            'branch_id': None,  # Oversees all branches
            'team_id': 'credit_team',
            'manager_id': None,
            'department': 'retail_banking',
            'permissions': json.dumps(ROLE_PERMISSIONS['credit_manager'])
        },
        
        # LOAN OFFICERS
        {
            'username': 'loan1',
            'password': 'pass123',
            'full_name': 'Rahul Mehta',
            'email': 'loan1@creditbridge.in',
            'employee_code': 'LO001',
            'role': 'loan_officer',
            'branch_id': downtown_id,
            'team_id': 'credit_team_downtown',
            'manager_id': None,
            'department': 'retail_banking',
            'permissions': json.dumps(ROLE_PERMISSIONS['loan_officer'])
        },
        {
            'username': 'loan2',
            'password': 'pass123',
            'full_name': 'Anita Nair',
            'email': 'loan2@creditbridge.in',
            'employee_code': 'LO002',
            'role': 'loan_officer',
            'branch_id': andheri_id,
            'team_id': 'credit_team_andheri',
            'manager_id': None,
            'department': 'retail_banking',
            'permissions': json.dumps(ROLE_PERMISSIONS['loan_officer'])
        },
        
        # CREDIT ANALYSTS
        {
            'username': 'analyst1',
            'password': 'pass123',
            'full_name': 'Meera Krishnan',
            'email': 'analyst1@creditbridge.in',
            'employee_code': 'CA001',
            'role': 'credit_analyst',
            'branch_id': downtown_id,
            'team_id': 'credit_team_downtown',
            'manager_id': None,
            'department': 'risk_analysis',
            'permissions': json.dumps(ROLE_PERMISSIONS['credit_analyst'])
        },
        {
            'username': 'analyst2',
            'password': 'pass123',
            'full_name': 'Arun Kumar',
            'email': 'analyst2@creditbridge.in',
            'employee_code': 'CA002',
            'role': 'credit_analyst',
            'branch_id': andheri_id,
            'team_id': 'credit_team_andheri',
            'manager_id': None,
            'department': 'risk_analysis',
            'permissions': json.dumps(ROLE_PERMISSIONS['credit_analyst'])
        }
    ]
    
    # Create employees
    for emp_data in employees:
        employee = Employee(
            username=emp_data['username'],
            password_hash=generate_password_hash(emp_data['password']),
            full_name=emp_data['full_name'],
            email=emp_data.get('email'),
            employee_code=emp_data.get('employee_code'),
            role=emp_data['role'],
            branch_id=emp_data.get('branch_id'),
            team_id=emp_data.get('team_id'),
            manager_id=emp_data.get('manager_id'),
            department=emp_data.get('department', 'retail_banking'),
            permissions=emp_data['permissions'],
            status='ACTIVE'
        )
        db.session.add(employee)
    
    db.session.commit()
    
    # Now set up manager relationships
    head_of_bank = Employee.query.filter_by(username='admin').first()
    branch_mgr_downtown = Employee.query.filter_by(username='manager1').first()
    branch_mgr_andheri = Employee.query.filter_by(username='manager2').first()
    credit_mgr = Employee.query.filter_by(username='credit').first()
    
    # Branch managers report to head of bank
    if head_of_bank and branch_mgr_downtown:
        branch_mgr_downtown.manager_id = head_of_bank.id
    if head_of_bank and branch_mgr_andheri:
        branch_mgr_andheri.manager_id = head_of_bank.id
    
    # Credit manager reports to head of bank (oversees all branches)
    if head_of_bank and credit_mgr:
        credit_mgr.manager_id = head_of_bank.id
    
    # Loan officers and analysts report to credit manager
    if credit_mgr:
        for emp in Employee.query.filter(Employee.role.in_(['loan_officer', 'credit_analyst'])).all():
            emp.manager_id = credit_mgr.id
    
    # Update branch managers in Branch table
    if downtown and branch_mgr_downtown:
        downtown.manager_id = branch_mgr_downtown.id
    if andheri and branch_mgr_andheri:
        andheri.manager_id = branch_mgr_andheri.id
    
    db.session.commit()
    print("✓ Seeded 8 demo employees with 5-role hierarchy")


def seed_sample_assessments():
    """Seed sample assessments for testing"""
    # Check if assessments already exist
    if CreditAssessment.query.count() > 0:
        return
    
    # Get employees for bank assessments (use new simplified usernames)
    branch_manager = Employee.query.filter_by(username='manager1').first()
    loan_officer = Employee.query.filter_by(username='loan1').first()
    
    if not branch_manager:
        print("⚠ No employees found, skipping assessment seed")
        return
    
    # Sample assessment data
    sample_data = [
        # Bank Portal Assessment 1 - Low Risk
        {
            'name': 'Priya Sharma',
            'phone': '9876543210',
            'email': 'priya.sharma@example.com',
            'pan_card': 'ABCDE1234F',
            'monthly_income': 85000,
            'monthly_expenses': 35000,
            'credit_score': 782,
            'risk_category': 'Low',
            'repayment_probability': 0.92,
            'is_bank': True,
            'status': 'approved'
        },
        # Bank Portal Assessment 2 - Medium Risk
        {
            'name': 'Rahul Verma',
            'phone': '9123456789',
            'email': 'rahul.verma@example.com',
            'pan_card': 'FGHIJ5678K',
            'monthly_income': 45000,
            'monthly_expenses': 30000,
            'credit_score': 625,
            'risk_category': 'Medium',
            'repayment_probability': 0.72,
            'is_bank': True,
            'status': 'pending_approval'
        },
        # Bank Portal Assessment 3 - Draft
        {
            'name': 'Anita Desai',
            'phone': '9988776655',
            'email': 'anita.desai@example.com',
            'pan_card': 'KLMNO9012L',
            'monthly_income': 120000,
            'monthly_expenses': 50000,
            'credit_score': 810,
            'risk_category': 'Low',
            'repayment_probability': 0.95,
            'is_bank': True,
            'status': 'draft'
        },
        # Public Portal Assessment 1
        {
            'name': 'Vikram Singh',
            'phone': '8877665544',
            'email': 'vikram.singh@gmail.com',
            'pan_card': 'PQRST3456M',
            'monthly_income': 55000,
            'monthly_expenses': 25000,
            'credit_score': 698,
            'risk_category': 'Medium',
            'repayment_probability': 0.78,
            'is_bank': False,
            'status': 'Completed'
        },
        # Public Portal Assessment 2
        {
            'name': 'Meera Krishnan',
            'phone': '7766554433',
            'email': 'meera.k@gmail.com',
            'pan_card': 'UVWXY7890N',
            'monthly_income': 95000,
            'monthly_expenses': 40000,
            'credit_score': 756,
            'risk_category': 'Low',
            'repayment_probability': 0.88,
            'is_bank': False,
            'status': 'Completed'
        }
    ]
    
    for data in sample_data:
        # Create User (Applicant)
        user = User(
            name=data['name'],
            phone=data['phone'],
            email=data['email'],
            pan_card=data['pan_card']
        )
        db.session.add(user)
        db.session.flush()
        
        # Create Financial Profile
        profile = FinancialProfile(
            user_id=user.id,
            monthly_income=data['monthly_income'],
            monthly_expenses=data['monthly_expenses'],
            income_std_dev=data['monthly_income'] * 0.1,
            upi_transaction_count=random.randint(20, 100),
            bill_payment_streak=random.randint(6, 24),
            digital_activity_months=random.randint(12, 36),
            savings_amount=data['monthly_income'] * random.uniform(2, 5)
        )
        db.session.add(profile)
        db.session.flush()
        
        # Create Credit Assessment
        features = {
            'behavioral': {
                'income_stability_index': random.uniform(0.6, 0.95),
                'expense_control_ratio': 1 - (data['monthly_expenses'] / data['monthly_income']),
                'payment_consistency_score': random.uniform(0.7, 0.98),
                'digital_activity_score': random.uniform(0.5, 0.9),
                'savings_discipline_ratio': random.uniform(0.15, 0.35),
                'cashflow_health_score': random.uniform(0.6, 0.9)
            },
            'confidence_level': random.uniform(0.75, 0.95),
            'model_used': 'XGBoost'
        }
        
        assessment = CreditAssessment(
            user_id=user.id,
            profile_id=profile.id,
            credit_score=data['credit_score'],
            risk_category=data['risk_category'],
            repayment_probability=data['repayment_probability'],
            features_json=json.dumps(features),
            status=data['status'],
            priority='normal',
            created_by=branch_manager.id if data['is_bank'] else None,
            processed_by=branch_manager.id if data['is_bank'] else None
        )
        
        # Set approved_by if approved
        if data['status'] == 'approved':
            assessment.approved_by = branch_manager.id
            assessment.approved_at = datetime.utcnow()
        
        db.session.add(assessment)
    
    db.session.commit()
    print(f"✓ Seeded {len(sample_data)} sample assessments")


# Application startup
def create_app():
    """Initialize application"""
    global ml_model, document_analyzer, pdf_generator
    
    # Create folders
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['REPORTS_FOLDER'], exist_ok=True)
    os.makedirs('models', exist_ok=True)
    
    with app.app_context():
        # Create database tables
        db.create_all()
        print("✓ Database tables created")
        
        # Seed employees
        seed_employees()
        
        # Seed sample assessments
        seed_sample_assessments()
        
        # Initialize ML model
        print("Initializing ML model...")
        ml_model = initialize_model()
        print("✓ ML model ready")
        
        # Initialize document analyzer
        gemini_key = os.getenv('GEMINI_API_KEY')
        document_analyzer = DocumentAnalyzer(gemini_key)
        print("✓ Document analyzer ready")
        
        # Initialize PDF generator
        pdf_generator = CreditReportGenerator()
        print("✓ PDF generator ready")

if __name__ == '__main__':
    create_app()
    
    print("\n" + "="*50)
    print("CREDITBRIDGE APPLICATION STARTED")
    print("="*50)
    print("🌐 Application URL: http://localhost:5000")
    print("\n📋 Demo Bank Logins (Password: pass123)")
    print("   admin      - Head of Bank")
    print("   manager1   - Branch Manager (Mumbai)")
    print("   manager2   - Branch Manager (Andheri)")
    print("   credit     - Credit Manager")
    print("   loan1      - Loan Officer (Mumbai)")
    print("   loan2      - Loan Officer (Andheri)")
    print("   analyst1   - Credit Analyst (Mumbai)")
    print("   analyst2   - Credit Analyst (Andheri)")
    print("\n🔐 Public Portal: http://localhost:5000/")
    print("="*50)
    
    app.run(host='0.0.0.0', port=5000, debug=True)