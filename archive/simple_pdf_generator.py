"""
Simple PDF Report Generator - Minimal, Working Version
"""
import os
import tempfile
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
import json


def generate_simple_pdf_report(assessment, user):
    """
    Generate a simple PDF report for credit assessment.
    
    Args:
        assessment: CreditAssessment object
        user: User object
        
    Returns:
        str: Path to generated PDF file
    """
    # Create temporary PDF file
    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    
    # Create PDF document
    doc = SimpleDocTemplate(
        temp_pdf.name,
        pagesize=A4,
        rightMargin=50,
        leftMargin=50,
        topMargin=50,
        bottomMargin=50
    )
    
    # Get styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=HexColor('#6366F1'),
        alignment=TA_CENTER,
        spaceAfter=30
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=HexColor('#1F2937'),
        spaceAfter=12
    )
    
    # Build content
    story = []
    
    # Title
    story.append(Paragraph("CREDITBRIDGE", title_style))
    story.append(Paragraph("Credit Assessment Report", styles['Heading2']))
    story.append(Spacer(1, 20))
    
    # Credit Score Section
    story.append(Paragraph("Credit Score", heading_style))
    score_data = [
        ['Credit Score:', str(assessment.credit_score)],
        ['Risk Category:', assessment.risk_category],
        ['Repayment Probability:', f"{assessment.repayment_probability * 100:.1f}%"]
    ]
    score_table = Table(score_data, colWidths=[2*inch, 3*inch])
    score_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 20))
    
    # Applicant Details
    story.append(Paragraph("Applicant Details", heading_style))
    applicant_data = [
        ['Name:', user.name],
        ['Phone:', user.phone],
        ['Email:', user.email or 'Not provided'],
        ['PAN Card:', user.pan_card or 'Not provided']
    ]
    applicant_table = Table(applicant_data, colWidths=[2*inch, 3*inch])
    applicant_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(applicant_table)
    story.append(Spacer(1, 20))
    
    # Assessment Info
    story.append(Paragraph("Assessment Information", heading_style))
    
    # Parse features
    try:
        if isinstance(assessment.features_json, str):
            features = json.loads(assessment.features_json)
        else:
            features = assessment.features_json
    except:
        features = {}
    
    # Get metrics
    income_stability = features.get('income_stability_index', 0.5)
    expense_control = features.get('expense_control_ratio', 0.5)
    payment_consistency = features.get('payment_consistency_score', 0.5)
    
    metrics_data = [
        ['Metric', 'Score'],
        ['Income Stability', f"{income_stability * 100:.0f}%"],
        ['Expense Control', f"{expense_control * 100:.0f}%"],
        ['Payment Consistency', f"{payment_consistency * 100:.0f}%"]
    ]
    metrics_table = Table(metrics_data, colWidths=[2.5*inch, 2.5*inch])
    metrics_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#6366F1')),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#E5E7EB')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(metrics_table)
    story.append(Spacer(1, 30))
    
    # Footer
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
        ParagraphStyle('Footer', fontSize=9, alignment=TA_CENTER, textColor=HexColor('#6B7280'))
    ))
    story.append(Paragraph(
        "CreditBridge - AI-Powered Credit Assessment",
        ParagraphStyle('Footer2', fontSize=9, alignment=TA_CENTER, textColor=HexColor('#6B7280'))
    ))
    
    # Build PDF
    doc.build(story)
    
    return temp_pdf.name
