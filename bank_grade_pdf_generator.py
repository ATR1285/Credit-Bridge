"""
bank_grade_pdf_generator.py
Shim module that wraps BankGradePDFGenerator from pdf_generator.py.
app.py imports generate_bank_grade_report from here.
"""

from pdf_generator import BankGradePDFGenerator
import json


def generate_bank_grade_report(assessment, user, output_path=None):
    """
    Generate a bank-grade PDF credit report.

    Args:
        assessment: CreditAssessment ORM object (or dict)
        user: User ORM object (or dict)
        output_path: Optional path for the output PDF (ignored; returns temp path)

    Returns:
        str: Path to the generated PDF file
    """
    generator = BankGradePDFGenerator()

    # Build assessment_data dict from ORM object or plain dict
    if hasattr(assessment, '__dict__'):
        assessment_data = {
            'id': assessment.id,
            'credit_score': assessment.credit_score,
            'risk_category': assessment.risk_category,
            'repayment_probability': assessment.repayment_probability,
            'features_json': assessment.features_json,
            'assessment_date': assessment.assessment_date,
            'document_bonus': getattr(assessment, 'document_bonus', 0),
        }
    else:
        assessment_data = assessment

    # Build user_data dict from ORM object or plain dict
    if hasattr(user, '__dict__'):
        user_data = {
            'name': user.name,
            'phone': user.phone,
            'email': getattr(user, 'email', ''),
            'pan_card': getattr(user, 'pan_card', ''),
        }
    else:
        user_data = user

    # Determine processed_by string
    processed_by = None
    if hasattr(assessment, 'creator') and assessment.creator:
        processed_by = assessment.creator.full_name
    elif hasattr(assessment, 'approved_by') and assessment.approved_by:
        try:
            from app import Employee
            emp = Employee.query.get(assessment.approved_by)
            processed_by = emp.full_name if emp else None
        except Exception:
            pass

    return generator.generate_report(assessment_data, user_data, processed_by)
