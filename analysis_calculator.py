"""
Analysis Calculator Module
--------------------------
Calculates derived metrics and prepares context for the Bank Audit Result page.
Used to decouple complex logic from app.py.
"""

def prepare_analysis_context(assessment, features):
    """
    Prepare the analysis context required by bank/result.html template.
    
    Args:
        assessment (CreditAssessment): The assessment object
        features (dict): The features dictionary derived from features_json
        
    Returns:
        dict: Analysis context with confidence, health scores, and formatting
    """
    # 1. Calculate Confidence
    confidence = features.get('confidence_level', 0.75)
    confidence_pct = int(confidence * 100)
    
    # 2. detailed Document Metrics
    upi_txns = features.get('doc_upi_frequency', 0)
    total_txns = features.get('doc_transaction_count', 0)
    emi_amount = features.get('doc_monthly_loan_payments', 0)
    salary_detected = features.get('doc_salary_detected', False)
    avg_balance = features.get('doc_avg_balance', 0)
    
    # 3. Health Score (Derived from multiple factors)
    # Using credit score as base, adjusted by document verification
    health_score = assessment.credit_score
    
    # Determine Health Label & Color
    if health_score >= 750:
        health_label = "Excellent"
        health_color = "success"
    elif health_score >= 700:
        health_label = "Good"
        health_color = "success"
    elif health_score >= 600:
        health_label = "Fair"
        health_color = "warning"
    else:
        health_label = "Needs Attention"
        health_color = "danger"
        
    # 4. Generate Risk Reasons
    risk_reasons = []
    
    try:
        # Repayment Probability
        repayment_prob = assessment.repayment_probability
        if repayment_prob < 0.7:
             risk_reasons.append({
                'type': 'danger', 
                'text': f"Low repayment probability calculated at {int(repayment_prob*100)}%"
            })
        
        # Income Stability
        income_stability = features.get('income_stability_index', 0)
        if income_stability < 0.4:
            risk_reasons.append({
                'type': 'warning',
                'text': "Income stability index is below threshold (irregular cashflow)"
            })
        elif income_stability > 0.8:
            risk_reasons.append({
                'type': 'success',
                'text': "High income stability demonstrated over 6 months"
            })
            
        # Overdrafts
        overdrafts = features.get('doc_overdraft_count', 0)
        if overdrafts > 3:
            risk_reasons.append({
                'type': 'danger',
                'text': f"Frequent overdrafts detected ({overdrafts} events)"
            })
            
        # EMI Burden
        income = features.get('monthly_income', 1) 
        if income > 0 and (emi_amount / income) > 0.5:
             risk_reasons.append({
                'type': 'warning',
                'text': "High existing EMI burden (>50% of income)"
            })
            
    except Exception as e:
        # Fallback if calculations fail
        risk_reasons.append({'type': 'info', 'text': 'Detailed risk analysis unavailable'})

    # 5. Build and return the context object
    return {
        'confidence': confidence,
        'confidence_pct': confidence_pct,
        'health_score': health_score,
        'health_label': health_label,
        'health_color': health_color,
        'formatted': {
            'upi': f"{int(upi_txns)} txns",
            'transactions': f"{int(total_txns)}",
            'emi': f"₹{int(emi_amount):,}",
            'salary': "Yes" if salary_detected else "No",
            'avg_balance': f"₹{int(avg_balance):,}"
        },
        'risk_reasons': risk_reasons
    }
