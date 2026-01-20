"""Force seed employees in cloud database"""
from dotenv import load_dotenv
import os
load_dotenv()

import json
from werkzeug.security import generate_password_hash
from app import app, db, Employee, Branch, ROLE_PERMISSIONS

with app.app_context():
    print(f"Using database: {app.config['SQLALCHEMY_DATABASE_URI'][:50]}...")
    
    # Check current employee count
    count = Employee.query.count()
    print(f"Current employee count: {count}")
    
    if count > 0:
        print("Employees already exist. Updating passwords...")
        for emp in Employee.query.all():
            emp.password_hash = generate_password_hash('pass123')
        db.session.commit()
        print("✓ All passwords reset to 'pass123'")
    else:
        print("No employees found. Creating from scratch...")
        
        # Create branches first
        branches_data = [
            {'branch_code': 'BR001', 'branch_name': 'Mumbai Downtown Branch', 'city': 'Mumbai', 'state': 'Maharashtra'},
            {'branch_code': 'BR002', 'branch_name': 'Andheri West Branch', 'city': 'Mumbai', 'state': 'Maharashtra'},
        ]
        
        for b in branches_data:
            if not Branch.query.filter_by(branch_code=b['branch_code']).first():
                branch = Branch(**b)
                db.session.add(branch)
        db.session.commit()
        print("✓ Branches created")
        
        # Get branch IDs
        downtown = Branch.query.filter_by(branch_code='BR001').first()
        andheri = Branch.query.filter_by(branch_code='BR002').first()
        downtown_id = downtown.id if downtown else None
        andheri_id = andheri.id if andheri else None
        
        # Create employees
        employees = [
            {'username': 'admin', 'role': 'head_of_bank', 'full_name': 'Rajesh Kumar', 'branch_id': None},
            {'username': 'manager1', 'role': 'branch_manager', 'full_name': 'Sunita Patel', 'branch_id': downtown_id},
            {'username': 'manager2', 'role': 'branch_manager', 'full_name': 'Amit Deshmukh', 'branch_id': andheri_id},
            {'username': 'credit', 'role': 'credit_manager', 'full_name': 'Priya Sharma', 'branch_id': None},
            {'username': 'loan1', 'role': 'loan_officer', 'full_name': 'Rahul Mehta', 'branch_id': downtown_id},
            {'username': 'loan2', 'role': 'loan_officer', 'full_name': 'Anita Nair', 'branch_id': andheri_id},
            {'username': 'analyst1', 'role': 'credit_analyst', 'full_name': 'Meera Krishnan', 'branch_id': downtown_id},
            {'username': 'analyst2', 'role': 'credit_analyst', 'full_name': 'Arun Kumar', 'branch_id': andheri_id},
        ]
        
        for emp_data in employees:
            emp = Employee(
                username=emp_data['username'],
                password_hash=generate_password_hash('pass123'),
                full_name=emp_data['full_name'],
                email=f"{emp_data['username']}@creditbridge.in",
                role=emp_data['role'],
                branch_id=emp_data['branch_id'],
                permissions=json.dumps(ROLE_PERMISSIONS.get(emp_data['role'], [])),
                status='ACTIVE'
            )
            db.session.add(emp)
        
        db.session.commit()
        print("✓ Employees created")
    
    print("\n=== Current Employees ===")
    for emp in Employee.query.all():
        print(f"  {emp.username} / pass123 ({emp.role})")
