"""
Email notification service for CreditBridge.
Handles sending notifications for various events.
"""

import logging
from flask_mail import Mail, Message
from threading import Thread


logger = logging.getLogger(__name__)
mail = Mail()


def send_async_email(app, msg):
    """
    Send email asynchronously in background thread.
    
    Args:
        app: Flask application instance
        msg: Flask-Mail Message object
    """
    with app.app_context():
        try:
            mail.send(msg)
            logger.info(f"Email sent to {msg.recipients}")
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}", exc_info=True)


def send_email(app, subject, recipients, body, html=None):
    """
    Send email notification.
    
    Args:
        app: Flask application instance
        subject (str): Email subject
        recipients (list): List of recipient email addresses
        body (str): Plain text email body
        html (str, optional): HTML email body
    """
    if not app.config.get('MAIL_USERNAME'):
        logger.warning("Email notifications not configured - skipping email send")
        return
    
    try:
        msg = Message(
            subject=f"[CreditBridge] {subject}",
            sender=app.config['MAIL_DEFAULT_SENDER'],
            recipients=recipients
        )
        msg.body = body
        
        if html:
            msg.html = html
        
        # Send asynchronously
        Thread(target=send_async_email, args=(app, msg)).start()
        
    except Exception as e:
        logger.error(f"Error preparing email: {str(e)}", exc_info=True)


def send_assessment_assigned_notification(app, employee, assessment):
    """
    Notify employee when assessment is assigned to them.
    
    Args:
        app: Flask application instance
        employee: Employee object
        assessment: CreditAssessment object
    """
    if not employee.email:
        return
    
    subject = f"New Assessment Assigned - #{assessment.id}"
    
    body = f"""
Hello {employee.full_name},

You have been assigned a new credit assessment for review.

Assessment Details:
- ID: #{assessment.id}
- Applicant: {assessment.user.name if assessment.user else 'N/A'}
- Credit Score: {assessment.credit_score}
- Risk Category: {assessment.risk_category}
- Priority: {assessment.priority.upper()}

Please login to review the assessment:
{app.config.get('BASE_URL', 'http://localhost:5000')}/bank/assessment/{assessment.id}

Best regards,
CreditBridge System
"""
    
    html = f"""
<html>
<body>
    <h2>New Assessment Assigned</h2>
    <p>Hello {employee.full_name},</p>
    <p>You have been assigned a new credit assessment for review.</p>
    
    <h3>Assessment Details:</h3>
    <ul>
        <li><strong>ID:</strong> #{assessment.id}</li>
        <li><strong>Applicant:</strong> {assessment.user.name if assessment.user else 'N/A'}</li>
        <li><strong>Credit Score:</strong> {assessment.credit_score}</li>
        <li><strong>Risk Category:</strong> {assessment.risk_category}</li>
        <li><strong>Priority:</strong> <span style="color: {'red' if assessment.priority == 'urgent' else 'orange' if assessment.priority == 'high' else 'green'};">{assessment.priority.upper()}</span></li>
    </ul>
    
    <p>
        <a href="{app.config.get('BASE_URL', 'http://localhost:5000')}/bank/assessment/{assessment.id}" 
           style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
            Review Assessment
        </a>
    </p>
    
    <p>Best regards,<br>CreditBridge System</p>
</body>
</html>
"""
    
    send_email(app, subject, [employee.email], body, html)


def send_assessment_approved_notification(app, employee, assessment, approver):
    """
    Notify employee when their assessment is approved.
    
    Args:
        app: Flask application instance
        employee: Employee object (creator)
        assessment: CreditAssessment object
        approver: Employee object (who approved)
    """
    if not employee.email:
        return
    
    subject = f"Assessment Approved - #{assessment.id}"
    
    body = f"""
Hello {employee.full_name},

Your credit assessment has been approved.

Assessment Details:
- ID: #{assessment.id}
- Applicant: {assessment.user.name if assessment.user else 'N/A'}
- Credit Score: {assessment.credit_score}
- Approved by: {approver.full_name}

View assessment:
{app.config.get('BASE_URL', 'http://localhost:5000')}/bank/assessment/{assessment.id}

Best regards,
CreditBridge System
"""
    
    send_email(app, subject, [employee.email], body)


def send_assessment_rejected_notification(app, employee, assessment, rejector, reason):
    """
    Notify employee when their assessment is rejected.
    
    Args:
        app: Flask application instance
        employee: Employee object (creator)
        assessment: CreditAssessment object
        rejector: Employee object (who rejected)
        reason (str): Rejection reason
    """
    if not employee.email:
        return
    
    subject = f"Assessment Rejected - #{assessment.id}"
    
    body = f"""
Hello {employee.full_name},

Your credit assessment has been rejected.

Assessment Details:
- ID: #{assessment.id}
- Applicant: {assessment.user.name if assessment.user else 'N/A'}
- Credit Score: {assessment.credit_score}
- Rejected by: {rejector.full_name}
- Reason: {reason}

You may need to review and resubmit this assessment.

View assessment:
{app.config.get('BASE_URL', 'http://localhost:5000')}/bank/assessment/{assessment.id}

Best regards,
CreditBridge System
"""
    
    send_email(app, subject, [employee.email], body)


def send_password_reset_notification(app, employee, reset_token):
    """
    Send password reset email.
    
    Args:
        app: Flask application instance
        employee: Employee object
        reset_token (str): Password reset token
    """
    if not employee.email:
        return
    
    subject = "Password Reset Request"
    
    reset_url = f"{app.config.get('BASE_URL', 'http://localhost:5000')}/bank/reset-password/{reset_token}"
    
    body = f"""
Hello {employee.full_name},

You have requested to reset your password.

Click the link below to reset your password:
{reset_url}

This link will expire in 1 hour.

If you did not request this reset, please ignore this email.

Best regards,
CreditBridge System
"""
    
    html = f"""
<html>
<body>
    <h2>Password Reset Request</h2>
    <p>Hello {employee.full_name},</p>
    <p>You have requested to reset your password.</p>
    
    <p>
        <a href="{reset_url}" 
           style="background-color: #2196F3; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
            Reset Password
        </a>
    </p>
    
    <p><small>This link will expire in 1 hour.</small></p>
    <p><small>If you did not request this reset, please ignore this email.</small></p>
    
    <p>Best regards,<br>CreditBridge System</p>
</body>
</html>
"""
    
    send_email(app, subject, [employee.email], body, html)


def send_daily_summary(app, employee, stats):
    """
    Send daily performance summary to employee.
    
    Args:
        app: Flask application instance
        employee: Employee object
        stats (dict): Daily statistics
    """
    if not employee.email:
        return
    
    subject = f"Daily Summary - {stats.get('date', 'Today')}"
    
    body = f"""
Hello {employee.full_name},

Here's your daily performance summary:

Assessments Processed: {stats.get('assessments_processed', 0)}
Approved: {stats.get('approved', 0)}
Rejected: {stats.get('rejected', 0)}
Pending: {stats.get('pending', 0)}
Approval Rate: {stats.get('approval_rate', 0)}%

Keep up the great work!

Best regards,
CreditBridge System
"""
    
    send_email(app, subject, [employee.email], body)
