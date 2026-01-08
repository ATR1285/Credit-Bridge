"""
Debug script to check employee roles and team assignments
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, Employee, CreditAssessment

def debug_check():
    with app.app_context():
        print("\n" + "=" * 70)
        print("EMPLOYEE DEBUG INFO")
        print("=" * 70)
        
        employees = Employee.query.all()
        for emp in employees:
            print(f"\nName: {emp.full_name}")
            print(f"  Username: {emp.username}")
            print(f"  Role: '{emp.role}'")
            print(f"  Team ID: {emp.team_id}")
            print(f"  Branch ID: {emp.branch_id}")
            print(f"  Status: {emp.status}")
        
        print("\n" + "=" * 70)
        print("ASSESSMENT DEBUG INFO")
        print("=" * 70)
        
        assessments = CreditAssessment.query.all()
        if not assessments:
            print("\nNo assessments in database!")
        else:
            for a in assessments:
                print(f"\nAssessment #{a.id}")
                print(f"  Status: {a.status}")
                print(f"  Created By: {a.created_by}")
                print(f"  Assigned To: {a.assigned_to}")
                print(f"  Score: {a.credit_score}")
        
        print("\n" + "=" * 70)
        print("ROLE MATCHING CHECK")
        print("=" * 70)
        
        # Check credit analyst role format
        analysts = Employee.query.filter_by(role='credit_analyst').all()
        print(f"\nEmployees with role='credit_analyst': {len(analysts)}")
        for a in analysts:
            print(f"  - {a.full_name} (team: {a.team_id})")
        
        # Check other format
        analysts2 = Employee.query.filter_by(role='Credit Analyst').all()
        print(f"\nEmployees with role='Credit Analyst': {len(analysts2)}")
        for a in analysts2:
            print(f"  - {a.full_name} (team: {a.team_id})")

if __name__ == '__main__':
    debug_check()
