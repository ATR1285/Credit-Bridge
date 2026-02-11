"""
CreditBridge Permission Registry

Centralized, type-safe permission management with:
- Enum-based permission definitions
- Category grouping for audit/management
- Validation functions
- Role-based default permissions

Usage:
    from permissions import Permission, validate_permissions, ROLE_PERMISSIONS
    
    # Check if valid
    validate_permissions(['VIEW_ALL_ASSESSMENTS', 'APPROVE_ASSESSMENTS'])
    
    # Get role defaults
    perms = ROLE_PERMISSIONS['loan_officer']
"""
from enum import Enum, auto
from typing import List, Set, Optional
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# PERMISSION CATEGORIES
# ============================================================================

class PermissionCategory(Enum):
    """Permission categories for grouping and audit"""
    VIEW = "view"           # Read-only access
    EDIT = "edit"           # Modify data
    CREATE = "create"       # Create new records
    DELETE = "delete"       # Delete records
    APPROVE = "approve"     # Approval workflows
    MANAGE = "manage"       # Administrative actions
    REPORT = "report"       # Reporting and exports
    SYSTEM = "system"       # System configuration
    DANGEROUS = "dangerous" # High-risk permissions (restricted)


# ============================================================================
# PERMISSION ENUM - ALL VALID PERMISSIONS
# ============================================================================

class Permission(Enum):
    """
    All valid system permissions.
    
    Naming convention: ACTION_SCOPE
    - ACTION: What can be done (VIEW, EDIT, CREATE, DELETE, APPROVE, etc.)
    - SCOPE: What it applies to (ALL, BRANCH, TEAM, OWN, ASSIGNED)
    """
    
    # ==========================================
    # DANGEROUS - Restricted to head_of_bank ONLY
    # ==========================================
    SUPER_ADMIN = "SUPER_ADMIN"
    ALL = "ALL"
    
    # ==========================================
    # VIEW - Read access
    # ==========================================
    # Global scope
    VIEW_ALL_BRANCHES = "VIEW_ALL_BRANCHES"
    VIEW_ALL_ASSESSMENTS = "VIEW_ALL_ASSESSMENTS"
    VIEW_ALL_CUSTOMERS = "VIEW_ALL_CUSTOMERS"
    VIEW_ALL_EMPLOYEES = "VIEW_ALL_EMPLOYEES"
    VIEW_ALL_AUDIT_LOGS = "VIEW_ALL_AUDIT_LOGS"
    VIEW_SYSTEM_LOGS = "VIEW_SYSTEM_LOGS"
    
    # Branch scope
    VIEW_BRANCH_ASSESSMENTS = "VIEW_BRANCH_ASSESSMENTS"
    VIEW_BRANCH_CUSTOMERS = "VIEW_BRANCH_CUSTOMERS"
    VIEW_BRANCH_EMPLOYEES = "VIEW_BRANCH_EMPLOYEES"
    VIEW_BRANCH_ANALYTICS = "VIEW_BRANCH_ANALYTICS"
    VIEW_BRANCH_AUDIT_LOGS = "VIEW_BRANCH_AUDIT_LOGS"
    
    # Team scope
    VIEW_TEAM_ASSESSMENTS = "VIEW_TEAM_ASSESSMENTS"
    VIEW_TEAM_CUSTOMERS = "VIEW_TEAM_CUSTOMERS"
    VIEW_TEAM_PERFORMANCE = "VIEW_TEAM_PERFORMANCE"
    VIEW_PORTFOLIO_ANALYTICS = "VIEW_PORTFOLIO_ANALYTICS"
    VIEW_ANALYST_WORKLOAD = "VIEW_ANALYST_WORKLOAD"
    VIEW_ESCALATIONS = "VIEW_ESCALATIONS"
    
    # Own scope
    VIEW_OWN_ASSESSMENTS = "VIEW_OWN_ASSESSMENTS"
    VIEW_OWN_CUSTOMERS = "VIEW_OWN_CUSTOMERS"
    VIEW_OWN_PERFORMANCE = "VIEW_OWN_PERFORMANCE"
    VIEW_ASSESSMENT_STATUS = "VIEW_ASSESSMENT_STATUS"
    
    # Assigned scope
    VIEW_ASSIGNED_ASSESSMENTS = "VIEW_ASSIGNED_ASSESSMENTS"
    VIEW_ASSIGNED_CUSTOMERS = "VIEW_ASSIGNED_CUSTOMERS"
    VIEW_ADVANCED_ANALYTICS = "VIEW_ADVANCED_ANALYTICS"
    
    # Reports
    VIEW_AUDIT_LOGS = "VIEW_AUDIT_LOGS"
    VIEW_EXECUTIVE_DASHBOARD = "VIEW_EXECUTIVE_DASHBOARD"
    VIEW_COMPARATIVE_ANALYTICS = "VIEW_COMPARATIVE_ANALYTICS"
    VIEW_FRAUD_REPORTS = "VIEW_FRAUD_REPORTS"
    VIEW_REVENUE_ANALYTICS = "VIEW_REVENUE_ANALYTICS"
    VIEW_PORTFOLIO_RISK = "VIEW_PORTFOLIO_RISK"
    VIEW_APPROVAL_TRENDS = "VIEW_APPROVAL_TRENDS"
    
    # ==========================================
    # EDIT - Modify access
    # ==========================================
    EDIT_ANY_ASSESSMENT = "EDIT_ANY_ASSESSMENT"
    EDIT_BRANCH_ASSESSMENTS = "EDIT_BRANCH_ASSESSMENTS"
    EDIT_TEAM_ASSESSMENTS = "EDIT_TEAM_ASSESSMENTS"
    EDIT_OWN_DRAFT = "EDIT_OWN_DRAFT"
    EDIT_ASSIGNED_ASSESSMENTS = "EDIT_ASSIGNED_ASSESSMENTS"
    EDIT_BRANCH = "EDIT_BRANCH"
    EDIT_EMPLOYEE = "EDIT_EMPLOYEE"
    
    ADD_REVIEW_NOTES = "ADD_REVIEW_NOTES"
    ADD_ANALYSIS_NOTES = "ADD_ANALYSIS_NOTES"
    ADD_FRAUD_FLAGS = "ADD_FRAUD_FLAGS"
    ADD_APPLICANT_NOTES = "ADD_APPLICANT_NOTES"
    UPDATE_CUSTOMER_INFO = "UPDATE_CUSTOMER_INFO"
    
    # ==========================================
    # CREATE - Create access
    # ==========================================
    CREATE_ASSESSMENT = "CREATE_ASSESSMENT"
    CREATE_BRANCH = "CREATE_BRANCH"
    ADD_EMPLOYEE = "ADD_EMPLOYEE"
    UPLOAD_DOCUMENTS = "UPLOAD_DOCUMENTS"
    
    # ==========================================
    # DELETE - Delete access
    # ==========================================
    DELETE_ANY_RECORD = "DELETE_ANY_RECORD"
    DELETE_ASSESSMENT = "DELETE_ASSESSMENT"
    DELETE_DRAFT_ASSESSMENTS = "DELETE_DRAFT_ASSESSMENTS"
    DELETE_OWN_DRAFT = "DELETE_OWN_DRAFT"
    PURGE_DATA = "PURGE_DATA"
    
    # ==========================================
    # APPROVE - Approval workflows
    # ==========================================
    APPROVE_ASSESSMENTS = "APPROVE_ASSESSMENTS"
    REJECT_ASSESSMENTS = "REJECT_ASSESSMENTS"
    APPROVE_HIGH_RISK = "APPROVE_HIGH_RISK"
    APPROVE_HIGH_VALUE_LOANS = "APPROVE_HIGH_VALUE_LOANS"
    APPROVE_MEDIUM_VALUE_LOANS = "APPROVE_MEDIUM_VALUE_LOANS"
    APPROVE_POLICY_EXCEPTIONS = "APPROVE_POLICY_EXCEPTIONS"
    FINAL_APPROVAL_AUTHORITY = "FINAL_APPROVAL_AUTHORITY"
    BULK_APPROVE = "BULK_APPROVE"
    
    RECOMMEND_APPROVAL = "RECOMMEND_APPROVAL"
    RECOMMEND_REJECTION = "RECOMMEND_REJECTION"
    RECOMMEND_ESCALATION = "RECOMMEND_ESCALATION"
    RECOMMEND_OVERRIDE = "RECOMMEND_OVERRIDE"
    
    # ==========================================
    # MANAGE - Administrative
    # ==========================================
    MANAGE_BRANCHES = "MANAGE_BRANCHES"
    MANAGE_BRANCH_MANAGERS = "MANAGE_BRANCH_MANAGERS"
    MANAGE_BRANCH_EMPLOYEES = "MANAGE_BRANCH_EMPLOYEES"
    MANAGE_USERS = "MANAGE_USERS"
    MANAGE_SYSTEM_SETTINGS = "MANAGE_SYSTEM_SETTINGS"
    
    CLOSE_BRANCH = "CLOSE_BRANCH"
    DEACTIVATE_EMPLOYEE = "DEACTIVATE_EMPLOYEE"
    ASSIGN_TEAMS = "ASSIGN_TEAMS"
    ASSIGN_ASSESSMENTS = "ASSIGN_ASSESSMENTS"
    REASSIGN_ANY_ASSESSMENT = "REASSIGN_ANY_ASSESSMENT"
    REASSIGN_TEAM_ASSESSMENTS = "REASSIGN_TEAM_ASSESSMENTS"
    SET_EMPLOYEE_TARGETS = "SET_EMPLOYEE_TARGETS"
    SET_BRANCH_TARGETS = "SET_BRANCH_TARGETS"
    MENTOR_ANALYSTS = "MENTOR_ANALYSTS"
    HIRE_FIRE_EMPLOYEES = "HIRE_FIRE_EMPLOYEES"
    
    # ==========================================
    # OVERRIDE - Special authority
    # ==========================================
    OVERRIDE_ANY_DECISION = "OVERRIDE_ANY_DECISION"
    OVERRIDE_BRANCH_MANAGER = "OVERRIDE_BRANCH_MANAGER"
    OVERRIDE_DECISION = "OVERRIDE_DECISION"
    EMERGENCY_OVERRIDE = "EMERGENCY_OVERRIDE"
    
    # ==========================================
    # WORKFLOW - Process actions
    # ==========================================
    SUBMIT_FOR_REVIEW = "SUBMIT_FOR_REVIEW"
    SUBMIT_REVIEW = "SUBMIT_REVIEW"
    SUBMIT_TO_MANAGER = "SUBMIT_TO_MANAGER"
    RESUBMIT_REJECTED = "RESUBMIT_REJECTED"
    REQUEST_REASSIGNMENT = "REQUEST_REASSIGNMENT"
    REQUEST_ADDITIONAL_DOCUMENTS = "REQUEST_ADDITIONAL_DOCUMENTS"
    
    MARK_UNDER_REVIEW = "MARK_UNDER_REVIEW"
    COMPLETE_ANALYSIS = "COMPLETE_ANALYSIS"
    REVIEW_ANALYST_WORK = "REVIEW_ANALYST_WORK"
    ESCALATE_TO_BRANCH_MANAGER = "ESCALATE_TO_BRANCH_MANAGER"
    ESCALATE_TO_MANAGER = "ESCALATE_TO_MANAGER"
    FLAG_QUALITY_ISSUES = "FLAG_QUALITY_ISSUES"
    FLAG_FRAUD = "FLAG_FRAUD"
    FLAG_FOR_QUALITY_REVIEW = "FLAG_FOR_QUALITY_REVIEW"
    VERIFY_DOCUMENTS = "VERIFY_DOCUMENTS"
    
    # ==========================================
    # TOOLS - Feature access
    # ==========================================
    ACCESS_FRAUD_DETECTION_TOOLS = "ACCESS_FRAUD_DETECTION_TOOLS"
    ACCESS_DOCUMENT_VERIFICATION = "ACCESS_DOCUMENT_VERIFICATION"
    ACCESS_BEHAVIORAL_ANALYTICS = "ACCESS_BEHAVIORAL_ANALYTICS"
    ACCESS_DEVELOPER_TOOLS = "ACCESS_DEVELOPER_TOOLS"
    RUN_CUSTOM_ANALYSIS = "RUN_CUSTOM_ANALYSIS"
    
    # ==========================================
    # REPORTS - Export and download
    # ==========================================
    EXPORT_ALL_REPORTS = "EXPORT_ALL_REPORTS"
    EXPORT_BRANCH_REPORTS = "EXPORT_BRANCH_REPORTS"
    EXPORT_TEAM_REPORTS = "EXPORT_TEAM_REPORTS"
    DOWNLOAD_RESULT_PDF = "DOWNLOAD_RESULT_PDF"
    SEND_CUSTOMER_NOTIFICATION = "SEND_CUSTOMER_NOTIFICATION"
    
    # ==========================================
    # SYSTEM - Configuration
    # ==========================================
    CONFIGURE_SETTINGS = "CONFIGURE_SETTINGS"
    CONFIGURE_BRANCH_SETTINGS = "CONFIGURE_BRANCH_SETTINGS"
    CONFIGURE_CREDIT_POLICIES = "CONFIGURE_CREDIT_POLICIES"
    CONFIGURE_ML_MODEL = "CONFIGURE_ML_MODEL"


# ============================================================================
# PERMISSION METADATA
# ============================================================================

# Set of all valid permission strings
VALID_PERMISSIONS: Set[str] = {p.value for p in Permission}

# Permissions restricted to head_of_bank only
DANGEROUS_PERMISSIONS: Set[str] = {
    Permission.SUPER_ADMIN.value,
    Permission.ALL.value,
    Permission.PURGE_DATA.value,
    Permission.EMERGENCY_OVERRIDE.value,
    Permission.ACCESS_DEVELOPER_TOOLS.value,
}

# Permissions that require at least branch_manager
MANAGER_ONLY_PERMISSIONS: Set[str] = {
    Permission.OVERRIDE_DECISION.value,
    Permission.DELETE_ASSESSMENT.value,
    Permission.MANAGE_USERS.value,
    Permission.HIRE_FIRE_EMPLOYEES.value,
}


# ============================================================================
# PERMISSION CATEGORIES MAPPING
# ============================================================================

def get_permission_category(permission: str) -> PermissionCategory:
    """Get category for a permission based on naming convention."""
    if permission in DANGEROUS_PERMISSIONS:
        return PermissionCategory.DANGEROUS
    elif permission.startswith('VIEW_'):
        return PermissionCategory.VIEW
    elif permission.startswith('EDIT_') or permission.startswith('ADD_') or permission.startswith('UPDATE_'):
        return PermissionCategory.EDIT
    elif permission.startswith('CREATE_') or permission.startswith('UPLOAD_'):
        return PermissionCategory.CREATE
    elif permission.startswith('DELETE_') or permission.startswith('PURGE_'):
        return PermissionCategory.DELETE
    elif permission.startswith('APPROVE_') or permission.startswith('REJECT_') or permission.startswith('RECOMMEND_'):
        return PermissionCategory.APPROVE
    elif permission.startswith('MANAGE_') or permission.startswith('ASSIGN_') or permission.startswith('SET_'):
        return PermissionCategory.MANAGE
    elif permission.startswith('EXPORT_') or permission.startswith('DOWNLOAD_'):
        return PermissionCategory.REPORT
    elif permission.startswith('CONFIGURE_') or permission.startswith('ACCESS_'):
        return PermissionCategory.SYSTEM
    else:
        return PermissionCategory.SYSTEM  # Default


# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

class PermissionError(Exception):
    """Exception for permission-related errors."""
    pass


def validate_permission(permission: str) -> bool:
    """
    Validate a single permission string.
    
    Args:
        permission: Permission string to validate
        
    Returns:
        True if valid
        
    Raises:
        PermissionError: If permission is invalid
    """
    if permission not in VALID_PERMISSIONS:
        raise PermissionError(f"Invalid permission: '{permission}'. Not in registry.")
    return True


def validate_permissions(permissions: List[str], role: str = None) -> bool:
    """
    Validate a list of permissions.
    
    Args:
        permissions: List of permission strings
        role: Optional role to check dangerous permission restrictions
        
    Returns:
        True if all valid
        
    Raises:
        PermissionError: If any permission is invalid or restricted
    """
    if not permissions:
        return True
    
    for perm in permissions:
        # Check if permission exists
        if perm not in VALID_PERMISSIONS:
            raise PermissionError(f"Invalid permission: '{perm}'. Not in registry.")
        
        # Check dangerous permission restrictions
        if role and role != 'head_of_bank':
            if perm in DANGEROUS_PERMISSIONS:
                raise PermissionError(
                    f"Dangerous permission '{perm}' can only be assigned to head_of_bank"
                )
        
        # Check manager-only permissions
        if role and role not in ('head_of_bank', 'branch_manager'):
            if perm in MANAGER_ONLY_PERMISSIONS:
                raise PermissionError(
                    f"Permission '{perm}' requires at least branch_manager role"
                )
    
    return True


def normalize_permission(permission: str) -> Optional[str]:
    """
    Attempt to normalize a permission string.
    
    Args:
        permission: Permission string (possibly with wrong case)
        
    Returns:
        Normalized permission or None if not found
    """
    # Already valid
    if permission in VALID_PERMISSIONS:
        return permission
    
    # Try uppercase
    upper = permission.upper()
    if upper in VALID_PERMISSIONS:
        return upper
    
    # Not found
    return None


def clean_permissions(permissions: List[str]) -> List[str]:
    """
    Clean a permission list, removing invalid entries.
    
    Args:
        permissions: List of permission strings
        
    Returns:
        Cleaned list with only valid permissions
    """
    cleaned = []
    for perm in permissions:
        normalized = normalize_permission(perm)
        if normalized:
            cleaned.append(normalized)
        else:
            logger.warning(f"Removed invalid permission: {perm}")
    return cleaned


# ============================================================================
# ROLE-BASED DEFAULT PERMISSIONS
# ============================================================================

ROLE_PERMISSIONS = {
    'head_of_bank': [
        Permission.SUPER_ADMIN.value,
        Permission.ALL.value,
        
        # View Everything
        Permission.VIEW_ALL_BRANCHES.value,
        Permission.VIEW_ALL_ASSESSMENTS.value,
        Permission.VIEW_ALL_CUSTOMERS.value,
        Permission.VIEW_ALL_EMPLOYEES.value,
        Permission.VIEW_ALL_AUDIT_LOGS.value,
        Permission.VIEW_SYSTEM_LOGS.value,
        Permission.VIEW_EXECUTIVE_DASHBOARD.value,
        Permission.VIEW_COMPARATIVE_ANALYTICS.value,
        Permission.VIEW_FRAUD_REPORTS.value,
        Permission.VIEW_REVENUE_ANALYTICS.value,
        Permission.VIEW_AUDIT_LOGS.value,
        
        # Edit Everything
        Permission.EDIT_ANY_ASSESSMENT.value,
        Permission.OVERRIDE_ANY_DECISION.value,
        Permission.OVERRIDE_BRANCH_MANAGER.value,
        Permission.DELETE_ANY_RECORD.value,
        
        # Manage Everything
        Permission.MANAGE_BRANCHES.value,
        Permission.CREATE_BRANCH.value,
        Permission.EDIT_BRANCH.value,
        Permission.CLOSE_BRANCH.value,
        Permission.MANAGE_BRANCH_MANAGERS.value,
        Permission.HIRE_FIRE_EMPLOYEES.value,
        Permission.CONFIGURE_CREDIT_POLICIES.value,
        Permission.MANAGE_SYSTEM_SETTINGS.value,
        Permission.CONFIGURE_ML_MODEL.value,
        
        # Reports
        Permission.EXPORT_ALL_REPORTS.value,
        
        # Critical
        Permission.APPROVE_HIGH_VALUE_LOANS.value,
        Permission.EMERGENCY_OVERRIDE.value,
        Permission.PURGE_DATA.value,
        Permission.ACCESS_DEVELOPER_TOOLS.value,
        Permission.CONFIGURE_SETTINGS.value,
    ],
    
    'branch_manager': [
        Permission.ALL.value,
        
        # View
        Permission.VIEW_BRANCH_ASSESSMENTS.value,
        Permission.VIEW_BRANCH_CUSTOMERS.value,
        Permission.VIEW_BRANCH_EMPLOYEES.value,
        Permission.VIEW_BRANCH_ANALYTICS.value,
        Permission.VIEW_BRANCH_AUDIT_LOGS.value,
        Permission.VIEW_ALL_ASSESSMENTS.value,
        Permission.VIEW_ALL_CUSTOMERS.value,
        Permission.VIEW_AUDIT_LOGS.value,
        Permission.VIEW_TEAM_PERFORMANCE.value,
        Permission.VIEW_PORTFOLIO_RISK.value,
        
        # Edit
        Permission.EDIT_ANY_ASSESSMENT.value,
        Permission.EDIT_BRANCH_ASSESSMENTS.value,
        Permission.DELETE_ASSESSMENT.value,
        Permission.DELETE_DRAFT_ASSESSMENTS.value,
        Permission.OVERRIDE_DECISION.value,
        Permission.REASSIGN_ANY_ASSESSMENT.value,
        
        # Manage
        Permission.MANAGE_USERS.value,
        Permission.MANAGE_BRANCH_EMPLOYEES.value,
        Permission.ADD_EMPLOYEE.value,
        Permission.EDIT_EMPLOYEE.value,
        Permission.DEACTIVATE_EMPLOYEE.value,
        Permission.ASSIGN_TEAMS.value,
        Permission.SET_EMPLOYEE_TARGETS.value,
        
        # Approve
        Permission.APPROVE_HIGH_RISK.value,
        Permission.APPROVE_MEDIUM_VALUE_LOANS.value,
        Permission.APPROVE_POLICY_EXCEPTIONS.value,
        Permission.FINAL_APPROVAL_AUTHORITY.value,
        Permission.BULK_APPROVE.value,
        
        # Reports
        Permission.EXPORT_ALL_REPORTS.value,
        Permission.EXPORT_BRANCH_REPORTS.value,
        
        # Config
        Permission.CONFIGURE_SETTINGS.value,
        Permission.CONFIGURE_BRANCH_SETTINGS.value,
        Permission.SET_BRANCH_TARGETS.value,
    ],
    
    'credit_manager': [
        # View
        Permission.VIEW_TEAM_ASSESSMENTS.value,
        Permission.VIEW_TEAM_CUSTOMERS.value,
        Permission.VIEW_TEAM_PERFORMANCE.value,
        Permission.VIEW_PORTFOLIO_ANALYTICS.value,
        Permission.VIEW_ESCALATIONS.value,
        Permission.VIEW_ANALYST_WORKLOAD.value,
        Permission.VIEW_APPROVAL_TRENDS.value,
        
        # Edit
        Permission.EDIT_TEAM_ASSESSMENTS.value,
        Permission.ADD_REVIEW_NOTES.value,
        
        # Approve
        Permission.APPROVE_ASSESSMENTS.value,
        Permission.REJECT_ASSESSMENTS.value,
        Permission.RECOMMEND_OVERRIDE.value,
        
        # Manage
        Permission.REVIEW_ANALYST_WORK.value,
        Permission.REASSIGN_TEAM_ASSESSMENTS.value,
        Permission.ESCALATE_TO_BRANCH_MANAGER.value,
        Permission.FLAG_QUALITY_ISSUES.value,
        Permission.ASSIGN_ASSESSMENTS.value,
        Permission.MENTOR_ANALYSTS.value,
        
        # Reports
        Permission.EXPORT_TEAM_REPORTS.value,
    ],
    
    'loan_officer': [
        # Create & View
        Permission.CREATE_ASSESSMENT.value,
        Permission.VIEW_OWN_ASSESSMENTS.value,
        Permission.VIEW_OWN_CUSTOMERS.value,
        Permission.VIEW_OWN_PERFORMANCE.value,
        Permission.VIEW_ASSESSMENT_STATUS.value,
        
        # Edit
        Permission.EDIT_OWN_DRAFT.value,
        Permission.DELETE_OWN_DRAFT.value,
        Permission.UPLOAD_DOCUMENTS.value,
        Permission.UPDATE_CUSTOMER_INFO.value,
        Permission.ADD_APPLICANT_NOTES.value,
        
        # Workflow
        Permission.SUBMIT_FOR_REVIEW.value,
        Permission.RESUBMIT_REJECTED.value,
        Permission.REQUEST_REASSIGNMENT.value,
        
        # Customer
        Permission.DOWNLOAD_RESULT_PDF.value,
        Permission.SEND_CUSTOMER_NOTIFICATION.value,
    ],
    
    'credit_analyst': [
        # View
        Permission.VIEW_ASSIGNED_ASSESSMENTS.value,
        Permission.VIEW_ASSIGNED_CUSTOMERS.value,
        Permission.VIEW_ADVANCED_ANALYTICS.value,
        
        # Edit
        Permission.EDIT_ASSIGNED_ASSESSMENTS.value,
        Permission.ADD_ANALYSIS_NOTES.value,
        Permission.ADD_FRAUD_FLAGS.value,
        
        # Analysis
        Permission.MARK_UNDER_REVIEW.value,
        Permission.COMPLETE_ANALYSIS.value,
        Permission.RECOMMEND_APPROVAL.value,
        Permission.RECOMMEND_REJECTION.value,
        Permission.RECOMMEND_ESCALATION.value,
        
        # Tools
        Permission.ACCESS_FRAUD_DETECTION_TOOLS.value,
        Permission.ACCESS_DOCUMENT_VERIFICATION.value,
        Permission.ACCESS_BEHAVIORAL_ANALYTICS.value,
        Permission.RUN_CUSTOM_ANALYSIS.value,
        
        # Workflow
        Permission.SUBMIT_REVIEW.value,
        Permission.SUBMIT_TO_MANAGER.value,
        Permission.ESCALATE_TO_MANAGER.value,
        Permission.FLAG_FRAUD.value,
        Permission.FLAG_FOR_QUALITY_REVIEW.value,
        Permission.VERIFY_DOCUMENTS.value,
        Permission.REQUEST_ADDITIONAL_DOCUMENTS.value,
    ],
}


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_permissions_for_role(role: str) -> List[str]:
    """Get default permissions for a role."""
    return ROLE_PERMISSIONS.get(role, [])


def has_any_permission(user_permissions: List[str], required: List[str]) -> bool:
    """Check if user has ANY of the required permissions."""
    if 'ALL' in user_permissions or 'SUPER_ADMIN' in user_permissions:
        return True
    return any(p in user_permissions for p in required)


def has_all_permissions(user_permissions: List[str], required: List[str]) -> bool:
    """Check if user has ALL of the required permissions."""
    if 'ALL' in user_permissions or 'SUPER_ADMIN' in user_permissions:
        return True
    return all(p in user_permissions for p in required)


def list_permissions_by_category(category: PermissionCategory) -> List[str]:
    """Get all permissions in a category."""
    return [
        p.value for p in Permission 
        if get_permission_category(p.value) == category
    ]
