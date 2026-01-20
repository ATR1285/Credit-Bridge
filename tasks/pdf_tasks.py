"""
PDF Generation Background Tasks

Async task for generating bank-grade PDF credit reports.
Includes retry logic, status tracking, and error handling.
"""
import os
from datetime import datetime
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=15)
def generate_pdf_task(self, report_id: str, assessment_id: int, user_id: int) -> dict:
    """
    Generate PDF report in background.
    
    Args:
        report_id: UUID of the PDFReport record
        assessment_id: ID of the CreditAssessment
        user_id: ID of the User
        
    Returns:
        Dict with status and file path
    """
    from app import db, CreditAssessment, User, PDFReport
    from bank_grade_pdf_generator import generate_bank_grade_report
    
    logger.info(f"Starting PDF generation for assessment {assessment_id}")
    
    # Get the tracking record
    report = PDFReport.query.get(report_id)
    if not report:
        logger.error(f"PDFReport {report_id} not found")
        return {'status': 'failed', 'error': 'Report record not found'}
    
    # Update status to processing
    report.status = 'processing'
    report.started_at = datetime.utcnow()
    db.session.commit()
    
    try:
        # Fetch assessment and user
        assessment = CreditAssessment.query.get(assessment_id)
        user = User.query.get(user_id)
        
        if not assessment or not user:
            raise ValueError("Assessment or user not found")
        
        # Prepare output path
        from flask import current_app
        output_dir = os.path.join(current_app.root_path, 'reports')
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = os.path.join(output_dir, f'{report_id}.pdf')
        
        logger.info(f"Generating PDF to {output_path}")
        
        # Generate the PDF (this is the slow part)
        generate_bank_grade_report(assessment, user, output_path)
        
        # Verify file was created
        if not os.path.exists(output_path):
            raise RuntimeError("PDF file was not created")
        
        file_size = os.path.getsize(output_path)
        
        # Update status to complete
        report.status = 'complete'
        report.file_path = output_path
        report.file_size = file_size
        report.completed_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"PDF generation complete: {output_path} ({file_size} bytes)")
        
        return {
            'status': 'complete',
            'file_path': output_path,
            'file_size': file_size
        }
        
    except SoftTimeLimitExceeded:
        logger.error(f"PDF generation timed out for assessment {assessment_id}")
        report.status = 'failed'
        report.error_message = 'Generation timed out'
        db.session.commit()
        return {'status': 'failed', 'error': 'Timeout'}
        
    except Exception as e:
        logger.error(f"PDF generation failed: {str(e)}")
        
        # Check if we should retry
        if self.request.retries < self.max_retries:
            report.status = 'retrying'
            report.error_message = f"Retry {self.request.retries + 1}: {str(e)}"
            db.session.commit()
            
            # Retry with exponential backoff
            raise self.retry(exc=e, countdown=15 * (2 ** self.request.retries))
        else:
            # Max retries exceeded
            report.status = 'failed'
            report.error_message = str(e)
            report.completed_at = datetime.utcnow()
            db.session.commit()
            
            return {'status': 'failed', 'error': str(e)}


@shared_task
def cleanup_old_pdfs(days: int = 7) -> dict:
    """
    Clean up old generated PDFs.
    
    Args:
        days: Delete PDFs older than this many days
        
    Returns:
        Cleanup statistics
    """
    from app import db, PDFReport
    from datetime import timedelta
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    old_reports = PDFReport.query.filter(
        PDFReport.created_at < cutoff,
        PDFReport.status == 'complete'
    ).all()
    
    deleted_count = 0
    freed_bytes = 0
    
    for report in old_reports:
        if report.file_path and os.path.exists(report.file_path):
            try:
                file_size = os.path.getsize(report.file_path)
                os.remove(report.file_path)
                deleted_count += 1
                freed_bytes += file_size
            except Exception as e:
                logger.error(f"Failed to delete {report.file_path}: {e}")
        
        db.session.delete(report)
    
    db.session.commit()
    
    logger.info(f"Cleaned up {deleted_count} old PDFs, freed {freed_bytes / 1024:.1f} KB")
    
    return {
        'deleted': deleted_count,
        'freed_bytes': freed_bytes
    }
