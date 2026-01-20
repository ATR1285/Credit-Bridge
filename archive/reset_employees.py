"""Reset employees to new simple credentials"""
from dotenv import load_dotenv
import os
load_dotenv()

from werkzeug.security import generate_password_hash
from app import app, db, Employee, Branch, ROLE_PERMISSIONS
import json

with app.app_context():
    # Get existing employees with old usernames and update them
    username_map = {
        'head_of_bank': 'admin',
        'branch_manager_downtown': 'manager1', 
        'branch_manager_andheri': 'manager2',
        'credit_manager': 'credit',
        'loan_officer_downtown': 'loan1',
        'loan_officer_andheri': 'loan2',
        'credit_analyst': 'analyst1',
        'credit_analyst_andheri': 'analyst2',
        # Alternate old names
        'loan_officer': 'loan1',
    }
    
    password_hash = generate_password_hash('pass123')
    
    updated = 0
    for emp in Employee.query.all():
        old_username = emp.username
        
        # Check if username is already simple
        if old_username in ['admin', 'manager1', 'manager2', 'credit', 'loan1', 'loan2', 'analyst1', 'analyst2']:
            # Just update password
            emp.password_hash = password_hash
            print(f"  Updated password for: {old_username}")
            updated += 1
            continue
        
        # Map old username to new simple one
        if old_username in username_map:
            new_username = username_map[old_username]
            emp.username = new_username
            emp.password_hash = password_hash
            print(f"  Changed: {old_username} -> {new_username}")
            updated += 1
        else:
            # Unknown username - just update password
            emp.password_hash = password_hash
            print(f"  Updated password for unknown: {old_username}")
            updated += 1
    
    db.session.commit()
    print(f"\n✓ Updated {updated} employees")
    
    print("\nCurrent employees:")
    for emp in Employee.query.all():
        print(f"  - {emp.username} / pass123 ({emp.role})")
