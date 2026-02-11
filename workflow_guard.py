"""
Workflow Guard Functions

Central access control for assessment editing.
Use these in all routes that modify assessments.
"""
from flask import session, abort, jsonify, request
from functools import wraps


def can_edit_assessment(employee, assessment):
    """
    Central workflow guard for assessment editing.
    
    Returns:
        (bool, str): (can_edit, reason_if_denied)
    """
    # Check if assessment is frozen (approved/rejected)
    if assessment.is_frozen:
        return False, "Assessment is finalized and cannot be edited"
    
    # Check if locked by another user
    if assessment.is_locked_by_other(employee):
        lock_holder = assessment.get_lock_holder_name()
        return False, f"Assessment is being edited by {lock_holder}"
    
    # Role-based edit rules
    role = employee.role
    status = assessment.status
    
    # Head of bank can always override (with logging)
    if role == 'head_of_bank':
        return True, None
    
    # Branch manager with ALL permission can override
    if role == 'branch_manager' and employee.has_permission('ALL'):
        return True, None
    
    # Loan Officer: Only own drafts
    if role == 'loan_officer':
        if assessment.created_by != employee.id:
            return False, "You can only edit your own assessments"
        if status != 'draft':
            return False, "You can only edit drafts"
        return True, None
    
    # Credit Analyst: Only assigned and in review
    if role == 'credit_analyst':
        if assessment.assigned_to != employee.id:
            return False, "This assessment is not assigned to you"
        if status not in ('pending_review', 'under_review', 'submitted'):
            return False, f"Assessment in '{status}' status cannot be edited by analyst"
        return True, None
    
    # Credit Manager: Team assessments in review/approval stages
    if role == 'credit_manager':
        team_ids = [e.id for e in employee.get_team_members()]
        if assessment.created_by not in team_ids and assessment.assigned_to not in team_ids:
            return False, "This assessment is not from your team"
        if status not in ('reviewed', 'pending_approval', 'escalated'):
            return False, f"Assessment in '{status}' status cannot be edited by manager"
        return True, None
    
    return False, "You don't have permission to edit this assessment"


def require_assessment_edit(f):
    """
    Decorator that checks if current user can edit the assessment.
    Expects 'assessment_id' in route args.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        from app import Employee, CreditAssessment, AuditLog, db
        
        assessment_id = kwargs.get('assessment_id') or kwargs.get('id')
        if not assessment_id:
            abort(400, "Assessment ID required")
        
        employee = Employee.query.get(session.get('employee_id'))
        if not employee:
            abort(401)
        
        assessment = CreditAssessment.query.get(assessment_id)
        if not assessment:
            abort(404, "Assessment not found")
        
        can_edit, reason = can_edit_assessment(employee, assessment)
        
        if not can_edit:
            # Log the denied access attempt
            AuditLog.log(
                employee_id=employee.id,
                action='EDIT_DENIED',
                entity_type='assessment',
                entity_id=assessment_id,
                details={'reason': reason, 'status': assessment.status}
            )
            db.session.commit()
            
            # Return appropriate response
            if request.is_json:
                return jsonify({'error': reason, 'code': 'EDIT_DENIED'}), 403
            abort(403, reason)
        
        # Acquire lock for editing
        if not assessment.acquire_lock(employee):
            lock_holder = assessment.get_lock_holder_name()
            if request.is_json:
                return jsonify({
                    'error': f'Assessment locked by {lock_holder}',
                    'code': 'LOCKED'
                }), 423  # HTTP 423 Locked
            abort(423, f'Assessment locked by {lock_holder}')
        
        db.session.commit()
        
        return f(*args, **kwargs)
    return decorated


def override_assessment(employee, assessment, reason):
    """
    Allow manager to override normal workflow rules.
    
    Args:
        employee: Employee performing override
        assessment: Assessment being overridden
        reason: Mandatory reason for override
        
    Returns:
        (bool, str): (success, error_message)
    """
    from app import AuditLog, db
    from datetime import datetime
    
    # Only branch_manager or head_of_bank can override
    if employee.role not in ('branch_manager', 'head_of_bank'):
        return False, "Only managers can use override"
    
    if not reason or len(reason.strip()) < 10:
        return False, "Override reason must be at least 10 characters"
    
    # Record the override
    assessment.override_used = True
    assessment.override_reason = reason.strip()
    assessment.override_by = employee.id
    assessment.override_at = datetime.utcnow()
    
    # Log the override
    AuditLog.log(
        employee_id=employee.id,
        action='WORKFLOW_OVERRIDE',
        entity_type='assessment',
        entity_id=assessment.id,
        details={
            'reason': reason,
            'previous_status': assessment.status
        }
    )
    
    db.session.commit()
    return True, None
