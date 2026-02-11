"""
Detailed debug: Check team assignments and manually assign if needed
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, Employee, CreditAssessment, assign_assessment_to_analyst

def full_debug():
    with app.app_context():
        print("\n" + "=" * 70)
        print("ALL EMPLOYEES - TEAM ASSIGNMENTS")
        print("=" * 70)
        
        employees = Employee.query.all()
        for emp in employees:
            print(f"{emp.role:20} | {emp.full_name:25} | Team: {emp.team_id}")
        
        print("\n" + "=" * 70)
        print("ALL ASSESSMENTS")
        print("=" * 70)
        
        assessments = CreditAssessment.query.all()
        if not assessments:
            print("\n** NO ASSESSMENTS IN DATABASE **")
            print("You need to create at least one assessment as a Loan Officer!")
        else:
            for a in assessments:
                creator = Employee.query.get(a.created_by) if a.created_by else None
                assignee = Employee.query.get(a.assigned_to) if a.assigned_to else None
                print(f"\nAssessment #{a.id}:")
                print(f"  Status: {a.status}")
                print(f"  Created By: {creator.full_name if creator else 'None'} (ID: {a.created_by})")
                print(f"  Assigned To: {assignee.full_name if assignee else 'NOT ASSIGNED'}")
                print(f"  Credit Score: {a.credit_score}")

def manually_assign_all():
    """Manually assign all unassigned assessments"""
    with app.app_context():
        # Find unassigned assessments
        unassigned = CreditAssessment.query.filter(
            (CreditAssessment.assigned_to == None) | 
            (CreditAssessment.status == 'draft')
        ).all()
        
        print(f"\nFound {len(unassigned)} unassigned assessments")
        
        for assessment in unassigned:
            print(f"\nAssigning assessment #{assessment.id}...")
            success, assigned_id, msg = assign_assessment_to_analyst(
                assessment.id,
                loan_officer_id=assessment.created_by or assessment.processed_by
            )
            print(f"  Result: {msg}")
        
        db.session.commit()
        print("\n✓ All assessments assigned!")

if __name__ == '__main__':
    full_debug()
    
    if len(sys.argv) > 1 and sys.argv[1] == 'assign':
        manually_assign_all()
    else:
        print("\n" + "-" * 70)
        print("To manually assign all unassigned assessments, run:")
        print("  python debug_full.py assign")
