"""
Script to check and fix employee permissions in CreditBridge
"""
import os
import sys
import json

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, Employee

def check_permissions():
    """Check all employee permissions"""
    with app.app_context():
        print("\n" + "=" * 60)
        print("EMPLOYEE PERMISSIONS CHECK")
        print("=" * 60)
        
        employees = Employee.query.all()
        for emp in employees:
            perms = json.loads(emp.permissions) if emp.permissions else []
            print(f"\n{emp.full_name} ({emp.role})")
            print(f"  Username: {emp.username}")
            print(f"  Permissions: {perms}")
            print(f"  Has 'create': {'YES' if 'create' in perms else 'NO'}")

def fix_loan_officer_permissions():
    """Fix Loan Officer permissions to include 'create'"""
    with app.app_context():
        print("\n" + "=" * 60)
        print("FIXING LOAN OFFICER PERMISSIONS")
        print("=" * 60)
        
        # Find all loan officers
        loan_officers = Employee.query.filter(
            Employee.role.in_(['Loan Officer', 'loan_officer'])
        ).all()
        
        if not loan_officers:
            print("No Loan Officers found!")
            return
        
        for officer in loan_officers:
            perms = json.loads(officer.permissions) if officer.permissions else []
            print(f"\nBefore: {officer.full_name} - {perms}")
            
            # Add 'create' permission if missing
            if 'create' not in perms:
                perms.append('create')
                officer.permissions = json.dumps(perms)
                print(f"After:  {officer.full_name} - {perms}")
            else:
                print(f"Already has 'create' permission")
        
        db.session.commit()
        print("\n✓ Permissions updated successfully!")

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'fix':
        fix_loan_officer_permissions()
    else:
        check_permissions()
        print("\n\nRun with 'fix' argument to update permissions:")
        print("  python check_permissions.py fix")
