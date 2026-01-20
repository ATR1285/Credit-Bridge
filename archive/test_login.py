from dotenv import load_dotenv
import os
load_dotenv()

from werkzeug.security import check_password_hash
from app import app, db, Employee

with app.app_context():
    e = Employee.query.filter_by(username='admin').first()
    if e:
        print(f"Admin found: {e.username}")
        print(f"Full name: {e.full_name}")
        print(f"Password hash starts with: {e.password_hash[:30]}...")
        print(f"pass123 valid: {check_password_hash(e.password_hash, 'pass123')}")
    else:
        print("Admin NOT FOUND!")
        print("All employees:")
        for emp in Employee.query.all():
            print(f"  - {emp.username} ({emp.role})")
