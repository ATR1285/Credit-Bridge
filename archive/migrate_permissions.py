"""
Permission Migration Script

Run this once to:
1. Normalize existing permissions (fix casing)
2. Remove invalid permissions
3. Ensure consistency with Permission enum

Usage: python migrate_permissions.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
from app import app, db, Employee
from permissions import (
    VALID_PERMISSIONS, 
    normalize_permission, 
    clean_permissions,
    ROLE_PERMISSIONS
)


def migrate_permissions():
    """Migrate all employee permissions to validated format."""
    print("=" * 60)
    print("PERMISSION MIGRATION")
    print("=" * 60)
    
    with app.app_context():
        employees = Employee.query.all()
        
        migrated = 0
        issues = []
        
        for emp in employees:
            try:
                current_perms = json.loads(emp.permissions) if emp.permissions else []
            except json.JSONDecodeError:
                issues.append(f"  ⚠ {emp.username}: Invalid JSON in permissions")
                current_perms = []
            
            # Clean and normalize
            cleaned = clean_permissions(current_perms)
            
            # Check for changes
            removed = set(current_perms) - set(cleaned)
            if removed:
                issues.append(f"  ⚠ {emp.username}: Removed invalid: {removed}")
            
            # Update if changed
            if cleaned != current_perms:
                emp.permissions = json.dumps(cleaned)
                migrated += 1
                print(f"  ✓ Migrated {emp.username} ({emp.role})")
        
        if migrated > 0:
            db.session.commit()
        
        print(f"\n✓ Migrated {migrated} employees")
        
        if issues:
            print("\nIssues found:")
            for issue in issues:
                print(issue)
        
        # Verify all permissions are valid
        print("\n" + "=" * 60)
        print("VERIFICATION")
        print("=" * 60)
        
        all_valid = True
        for emp in employees:
            perms = json.loads(emp.permissions) if emp.permissions else []
            for p in perms:
                if p not in VALID_PERMISSIONS:
                    print(f"  ⚠ {emp.username}: Still has invalid permission: {p}")
                    all_valid = False
        
        if all_valid:
            print("  ✓ All permissions are valid!")
        
        print("\n" + "=" * 60)
        print("MIGRATION COMPLETE")
        print("=" * 60)


def reset_to_defaults():
    """Reset all employees to role-based default permissions."""
    print("=" * 60)
    print("RESET TO ROLE DEFAULTS")
    print("=" * 60)
    
    confirm = input("This will reset ALL permissions to role defaults. Continue? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Cancelled.")
        return
    
    with app.app_context():
        employees = Employee.query.all()
        
        for emp in employees:
            default_perms = ROLE_PERMISSIONS.get(emp.role, [])
            emp.permissions = json.dumps(default_perms)
            print(f"  ✓ Reset {emp.username} ({emp.role}) - {len(default_perms)} permissions")
        
        db.session.commit()
        print(f"\n✓ Reset {len(employees)} employees to defaults")


def audit_permissions():
    """Audit all permissions in the database."""
    print("=" * 60)
    print("PERMISSION AUDIT")
    print("=" * 60)
    
    with app.app_context():
        employees = Employee.query.all()
        
        all_perms = set()
        perm_usage = {}
        
        for emp in employees:
            perms = json.loads(emp.permissions) if emp.permissions else []
            for p in perms:
                all_perms.add(p)
                perm_usage[p] = perm_usage.get(p, 0) + 1
        
        print(f"\nUnique permissions in use: {len(all_perms)}")
        print(f"Valid permissions in registry: {len(VALID_PERMISSIONS)}")
        
        # Find invalid
        invalid = all_perms - VALID_PERMISSIONS
        if invalid:
            print(f"\n⚠ Invalid permissions found ({len(invalid)}):")
            for p in sorted(invalid):
                print(f"  - {p} (used by {perm_usage[p]} employees)")
        else:
            print("\n✓ No invalid permissions found")
        
        # Most used
        print("\nTop 10 most used permissions:")
        sorted_perms = sorted(perm_usage.items(), key=lambda x: -x[1])[:10]
        for perm, count in sorted_perms:
            valid = "✓" if perm in VALID_PERMISSIONS else "⚠"
            print(f"  {valid} {perm}: {count}")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == '--reset':
            reset_to_defaults()
        elif sys.argv[1] == '--audit':
            audit_permissions()
        else:
            print("Usage: python migrate_permissions.py [--reset|--audit]")
    else:
        migrate_permissions()
