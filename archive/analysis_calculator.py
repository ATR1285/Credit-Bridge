"""
Analysis Calculator

Computes Financial Health Score, Data Confidence, and Risk Reasons
for the Bank Statement Analysis section.
"""
import json


def compute_financial_health_score(features: dict) -> int:
    """
    Compute Financial Health Score (0-100) from assessment features.
    
    Weights:
    - Income stability: 25%
    - Expense control: 20%
    - Payment consistency: 20%
    - Savings discipline: 15%
    - Cashflow health: 10%
    - Digital activity: 10%
    """
    weights = {
        'income_stability_index': 25,
        'expense_control_ratio': 20,
        'payment_consistency_score': 20,
        'savings_discipline_ratio': 15,
        'cashflow_health_score': 10,
        'digital_activity_score': 10,
    }
    
    score = 0
    for key, weight in weights.items():
        value = features.get(key, 0.5)  # Default 0.5 if missing
        if isinstance(value, (int, float)):
            score += value * weight
    
    return min(100, max(0, int(score)))


def get_health_label(score: int) -> tuple:
    """Get label and color class for health score."""
    if score >= 70:
        return 'Good', 'success'
    elif score >= 40:
        return 'Medium', 'warning'
    else:
        return 'Poor', 'danger'


def compute_data_confidence(features: dict, documents: list = None) -> float:
    """
    Compute Data Confidence percentage (0.0-1.0).
    
    Based on:
    - Number of data points available
    - Document verification scores
    - Consistency of data
    """
    confidence = 0.0
    
    # Base: Feature availability (40%)
    key_features = [
        'income_stability_index', 'expense_control_ratio', 
        'payment_consistency_score', 'savings_discipline_ratio',
        'doc_transaction_count', 'doc_avg_balance'
    ]
    
    available = sum(1 for k in key_features if features.get(k) is not None)
    confidence += (available / len(key_features)) * 0.4
    
    # Document scores (30%)
    doc_keys = [
        'doc_income_verification_score', 'doc_identity_score',
        'doc_financial_health_score', 'doc_cross_verification_score'
    ]
    doc_scores = [features.get(k, 0) for k in doc_keys if features.get(k)]
    if doc_scores:
        confidence += (sum(doc_scores) / len(doc_scores)) * 0.3
    else:
        confidence += 0.15  # Partial credit if no docs
    
    # Transaction data richness (20%)
    txn_count = features.get('doc_transaction_count', 0)
    if txn_count >= 50:
        confidence += 0.2
    elif txn_count >= 20:
        confidence += 0.15
    elif txn_count >= 5:
        confidence += 0.1
    else:
        confidence += 0.05
    
    # Salary detection bonus (10%)
    if features.get('doc_salary_detected'):
        confidence += 0.1
    
    return min(1.0, confidence)


def generate_risk_reasons(features: dict, credit_score: int) -> list:
    """
    Generate human-readable risk reasons.
    
    Returns list of dicts: [{'type': 'warning|danger|info', 'text': '...'}]
    """
    reasons = []
    
    # Income stability
    isi = features.get('income_stability_index', 0)
    if isi < 0.4:
        reasons.append({
            'type': 'danger',
            'text': 'Irregular income pattern detected - high variability month to month'
        })
    elif isi < 0.6:
        reasons.append({
            'type': 'warning',
            'text': 'Moderate income stability - some fluctuations observed'
        })
    
    # Expense control
    ecr = features.get('expense_control_ratio', 0)
    if ecr < 0.3:
        reasons.append({
            'type': 'danger',
            'text': 'High expense-to-income ratio - limited disposable income'
        })
    elif ecr < 0.5:
        reasons.append({
            'type': 'warning',
            'text': 'Expenses consuming significant portion of income'
        })
    
    # Savings behavior
    sdr = features.get('savings_discipline_ratio', 0)
    if sdr < 0.1:
        reasons.append({
            'type': 'danger',
            'text': 'No regular savings pattern identified'
        })
    elif sdr < 0.3:
        reasons.append({
            'type': 'warning',
            'text': 'Low savings rate - limited financial buffer'
        })
    
    # Overdrafts and bounces
    overdrafts = features.get('doc_overdraft_count', 0)
    bounces = features.get('doc_bounce_count', 0)
    
    if overdrafts > 3:
        reasons.append({
            'type': 'danger',
            'text': f'{overdrafts} overdraft instances detected - cash flow stress'
        })
    elif overdrafts > 0:
        reasons.append({
            'type': 'warning',
            'text': f'{overdrafts} overdraft(s) in statement period'
        })
    
    if bounces > 0:
        reasons.append({
            'type': 'danger',
            'text': f'{bounces} bounced payment(s) - indicates payment difficulties'
        })
    
    # Salary detection
    if not features.get('doc_salary_detected'):
        reasons.append({
            'type': 'warning',
            'text': 'No regular salary credits identified'
        })
    
    # EMI burden
    emi = features.get('doc_emi_payments', 0)
    if emi > 5:
        reasons.append({
            'type': 'warning',
            'text': f'{emi} active EMI payments - existing loan burden'
        })
    
    # Add positive reasons if score is good
    if credit_score >= 700:
        if isi >= 0.7:
            reasons.append({
                'type': 'success',
                'text': 'Strong and consistent income pattern'
            })
        if features.get('doc_salary_detected'):
            reasons.append({
                'type': 'success',
                'text': 'Regular salary credits verified'
            })
        if bounces == 0 and overdrafts == 0:
            reasons.append({
                'type': 'success',
                'text': 'Clean payment history - no bounces or overdrafts'
            })
    
    return reasons


def get_verification_notes(features: dict) -> dict:
    """
    Generate verification notes for each document type.
    
    Returns dict: {'income_verification': 'note', ...}
    """
    notes = {}
    
    # Income verification
    income_score = features.get('doc_income_verification_score', 0.5)
    if income_score >= 0.8:
        notes['income_verification'] = 'Income documents fully verified'
    elif income_score >= 0.6:
        notes['income_verification'] = 'Partial match - minor discrepancies'
    else:
        notes['income_verification'] = 'Requires manual review - salary pattern unclear'
    
    # Identity verification
    id_score = features.get('doc_identity_score', 0.5)
    if id_score >= 0.8:
        notes['identity'] = 'Identity verified successfully'
    elif id_score >= 0.6:
        notes['identity'] = 'Minor name/address variations detected'
    else:
        notes['identity'] = 'Identity verification incomplete'
    
    # Financial health
    fin_score = features.get('doc_financial_health_score', 0.5)
    if fin_score >= 0.8:
        notes['financial_health'] = 'Strong financial indicators'
    elif fin_score >= 0.5:
        notes['financial_health'] = 'Average financial health indicators'
    else:
        notes['financial_health'] = 'Weak financial indicators detected'
    
    # Cross verification
    cross_score = features.get('doc_cross_verification_score', 0.5)
    if cross_score >= 0.8:
        notes['cross_verification'] = 'All documents cross-verified'
    elif cross_score >= 0.6:
        notes['cross_verification'] = 'Partial cross-verification completed'
    else:
        notes['cross_verification'] = 'Document inconsistencies found'
    
    return notes


def format_transaction_value(key: str, value, features: dict) -> str:
    """Format transaction values in human-friendly text."""
    
    if key == 'doc_upi_frequency':
        if value == 0 or value is None:
            return 'No UPI activity'
        elif value < 10:
            return f'{value} transactions'
        else:
            return f'{value} (Active)'
    
    elif key == 'doc_emi_payments':
        if value == 0 or value is None:
            return 'None detected'
        else:
            return f'{value} active'
    
    elif key == 'doc_salary_detected':
        return 'Verified' if value else 'Not found'
    
    elif key == 'doc_transaction_count':
        if value == 0 or value is None:
            return 'No data'
        elif value < 10:
            return f'{value} (Low)'
        elif value < 50:
            return f'{value}'
        else:
            return f'{value} (High activity)'
    
    elif key == 'doc_avg_balance':
        if value == 0 or value is None:
            return 'No data'
        return f'₹{value:,.0f}'
    
    return str(value) if value else 'N/A'


def prepare_analysis_context(assessment, features: dict) -> dict:
    """
    Prepare complete analysis context for template.
    
    Call this from the route and pass to template.
    """
    health_score = compute_financial_health_score(features)
    health_label, health_color = get_health_label(health_score)
    confidence = compute_data_confidence(features)
    risk_reasons = generate_risk_reasons(features, assessment.credit_score)
    verification_notes = get_verification_notes(features)
    
    return {
        'health_score': health_score,
        'health_label': health_label,
        'health_color': health_color,
        'confidence': confidence,
        'confidence_pct': int(confidence * 100),
        'risk_reasons': risk_reasons,
        'verification_notes': verification_notes,
        'formatted': {
            'upi': format_transaction_value('doc_upi_frequency', features.get('doc_upi_frequency', 0), features),
            'emi': format_transaction_value('doc_emi_payments', features.get('doc_emi_payments', 0), features),
            'salary': format_transaction_value('doc_salary_detected', features.get('doc_salary_detected'), features),
            'transactions': format_transaction_value('doc_transaction_count', features.get('doc_transaction_count', 0), features),
            'avg_balance': format_transaction_value('doc_avg_balance', features.get('doc_avg_balance', 0), features),
        }
    }
