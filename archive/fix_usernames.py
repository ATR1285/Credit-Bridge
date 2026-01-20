"""Fix all employee usernames to simple format"""
from dotenv import load_dotenv
load_dotenv()

from werkzeug.security import generate_password_hash
from app import app, db, Employee

# Mapping of old -> new usernames
USERNAME_FIXES = {
    'branch_manager': 'manager1',
    'branch_manager_downtown': 'manager1',
    'branch_manager_andheri': 'manager2',
    'credit_manager': 'credit',
    'credit_manager_andheri': 'credit',  # duplicate - will skip
    'loan_officer': 'loan1',
    'loan_officer_2': 'loan2',
    'loan_officer_downtown': 'loan1',
    'loan_officer_andheri': 'loan2',
    'credit_analyst': 'analyst1',
    'credit_analyst_2': 'analyst2',
    'credit_analyst_downtown': 'analyst1',
    'credit_analyst_andheri': 'analyst2',
}

# Target usernames we want
TARGET_USERNAMES = ['admin', 'manager1', 'manager2', 'credit', 'loan1', 'loan2', 'analyst1', 'analyst2']

with app.app_context():
    password_hash = generate_password_hash('pass123')
    
    # First, update passwords for all employees
    for emp in Employee.query.all():
        emp.password_hash = password_hash
    
    # Find employees with old usernames and rename them
    for old_name, new_name in USERNAME_FIXES.items():
        emp = Employee.query.filter_by(username=old_name).first()
        if emp:
            # Check if new username already exists
            existing = Employee.query.filter_by(username=new_name).first()
            if existing and existing.id != emp.id:
                # Delete duplicate
                print(f"  Deleting duplicate: {old_name}")
                db.session.delete(emp)
            else:
                print(f"  Renaming: {old_name} -> {new_name}")
                emp.username = new_name
    
    db.session.commit()
    
    print("\n=== Final Employee List ===")
    for emp in Employee.query.order_by(Employee.role).all():
        status = "✓" if emp.username in TARGET_USERNAMES else "?"
        print(f"  {status} {emp.username} / pass123 ({emp.role})")
