"""
ALL Permission Cleanup Script

Removes dangerous permissions (ALL, SUPER_ADMIN) from employees
who shouldn't have them based on their role.

Usage: python cleanup_all_permission.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
from app import app, db, Employee, AuditLog


# Rules: which roles are allowed which dangerous permissions
ALLOWED_DANGEROUS_PERMS = {
    'head_of_bank': {'ALL', 'SUPER_ADMIN', 'PURGE_DATA', 'EMERGENCY_OVERRIDE'},
    'branch_manager': {'ALL'},  # Only ALL, not SUPER_ADMIN
    'credit_manager': set(),    # No dangerous permissions
    'loan_officer': set(),
    'credit_analyst': set(),
}


def cleanup_dangerous_permissions():
    """Remove dangerous permissions from unauthorized roles."""
    print("=" * 60)
    print("ALL PERMISSION SECURITY CLEANUP")
    print("=" * 60)
    
    with app.app_context():
        employees = Employee.query.all()
        
        fixed = 0
        issues = []
        
        for emp in employees:
            try:
                perms = json.loads(emp.permissions) if emp.permissions else []
            except json.JSONDecodeError:
                issues.append(f"⚠ {emp.username}: Invalid JSON")
                continue
            
            allowed = ALLOWED_DANGEROUS_PERMS.get(emp.role, set())
            removed = []
            
            # Check each permission
            new_perms = []
            for p in perms:
                if p in ('ALL', 'SUPER_ADMIN', 'PURGE_DATA', 'EMERGENCY_OVERRIDE'):
                    if p not in allowed:
                        removed.append(p)
                        print(f"  ⚠ {emp.username} ({emp.role}): Removing '{p}'")
                    else:
                        new_perms.append(p)
                else:
                    new_perms.append(p)
            
            if removed:
                emp.permissions = json.dumps(new_perms)
                
                # Log the change
                AuditLog.log(
                    employee_id=None,  # System action
                    action='SECURITY_CLEANUP',
                    entity_type='employee',
                    entity_id=emp.id,
                    before={'permissions': perms},
                    after={'permissions': new_perms},
                    details={
                        'removed_permissions': removed,
                        'reason': 'Dangerous permission not allowed for role'
                    }
                )
                fixed += 1
        
        if fixed > 0:
            db.session.commit()
            print(f"\n✓ Fixed {fixed} employees")
        else:
            print("\n✓ No issues found - all permissions are correctly assigned")
        
        # Summary
        print("\n" + "=" * 60)
        print("CURRENT DANGEROUS PERMISSION USAGE")
        print("=" * 60)
        
        for role in ALLOWED_DANGEROUS_PERMS.keys():
            employees_with_role = Employee.query.filter_by(role=role).all()
            for emp in employees_with_role:
                perms = json.loads(emp.permissions) if emp.permissions else []
                dangerous = [p for p in perms if p in ('ALL', 'SUPER_ADMIN')]
                if dangerous:
                    status = "✓" if set(dangerous) <= ALLOWED_DANGEROUS_PERMS[role] else "⚠"
                    print(f"  {status} {emp.username} ({role}): {dangerous}")
        
        print("\n" + "=" * 60)
        print("CLEANUP COMPLETE")
        print("=" * 60)


if __name__ == '__main__':
    cleanup_dangerous_permissions()
