"""
One-time database hierarchy fixer script.

Run this to fix any invalid manager relationships where
a lower-ranked employee is managing a higher-ranked one.

Usage: python fix_hierarchy.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, Employee, ROLE_LEVELS


def fix_hierarchy():
    """Fix invalid manager relationships in database."""
    print("=" * 50)
    print("CREDITBRIDGE HIERARCHY FIXER")
    print("=" * 50)
    
    with app.app_context():
        employees = Employee.query.all()
        fixed_count = 0
        
        for emp in employees:
            if emp.manager_id:
                manager = Employee.query.get(emp.manager_id)
                
                if manager:
                    try:
                        # Check if manager can actually manage this employee
                        if not manager.can_manage(emp):
                            print(f"⚠ INVALID: {manager.username} ({manager.role}) "
                                  f"cannot manage {emp.username} ({emp.role})")
                            print(f"   → Removing invalid manager assignment")
                            emp.manager_id = None
                            fixed_count += 1
                            
                        # Check branch constraint
                        elif (manager.branch_id != emp.branch_id and 
                              manager.role != "head_of_bank"):
                            print(f"⚠ CROSS-BRANCH: {emp.username} managed by "
                                  f"{manager.username} (different branch)")
                            print(f"   → Removing cross-branch manager")
                            emp.manager_id = None
                            fixed_count += 1
                            
                    except Exception as e:
                        print(f"⚠ Error checking {emp.username}: {e}")
                else:
                    print(f"⚠ ORPHAN: {emp.username} has invalid manager_id {emp.manager_id}")
                    emp.manager_id = None
                    fixed_count += 1
        
        if fixed_count > 0:
            db.session.commit()
            print(f"\n✓ Fixed {fixed_count} invalid manager assignments")
        else:
            print("\n✓ All manager relationships are valid")
        
        # Print current hierarchy
        print("\n" + "=" * 50)
        print("CURRENT HIERARCHY")
        print("=" * 50)
        
        for level in sorted(ROLE_LEVELS.items(), key=lambda x: -x[1]):
            role, lvl = level
            emps = Employee.query.filter_by(role=role).all()
            if emps:
                print(f"\n[Level {lvl}] {role.upper()}")
                for e in emps:
                    manager_info = ""
                    if e.manager_id:
                        mgr = Employee.query.get(e.manager_id)
                        if mgr:
                            manager_info = f" (managed by: {mgr.username})"
                    print(f"   • {e.username}{manager_info}")
        
        print("\n" + "=" * 50)
        print("HIERARCHY FIX COMPLETE")
        print("=" * 50)


if __name__ == '__main__':
    fix_hierarchy()
