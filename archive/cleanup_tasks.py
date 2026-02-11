"""
Utility functions for file cleanup and maintenance tasks.
"""

import os
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger


logger = logging.getLogger(__name__)


def cleanup_old_files(app, db, DocumentUpload):
    """
    Clean up old uploaded files based on retention policy.
    
    Args:
        app: Flask application instance
        db: Database instance
        DocumentUpload: DocumentUpload model class
    """
    with app.app_context():
        try:
            retention_days = app.config.get('FILE_RETENTION_DAYS', 90)
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            
            logger.info(f"Starting file cleanup - deleting files older than {retention_days} days")
            
            # Find old documents
            old_documents = DocumentUpload.query.filter(
                DocumentUpload.uploaded_at < cutoff_date
            ).all()
            
            deleted_count = 0
            error_count = 0
            
            for doc in old_documents:
                try:
                    # Delete physical file
                    if doc.file_path and os.path.exists(doc.file_path):
                        os.remove(doc.file_path)
                        logger.debug(f"Deleted file: {doc.file_path}")
                    
                    # Delete database record
                    db.session.delete(doc)
                    deleted_count += 1
                    
                except Exception as e:
                    error_count += 1
                    logger.error(f"Error deleting document {doc.id}: {str(e)}")
                    db.session.rollback()
                    continue
            
            # Commit all deletions
            db.session.commit()
            
            logger.info(f"File cleanup completed - Deleted: {deleted_count}, Errors: {error_count}")
            
        except Exception as e:
            logger.error(f"File cleanup failed: {str(e)}", exc_info=True)
            db.session.rollback()


def cleanup_old_reports(app):
    """
    Clean up old generated PDF reports.
    
    Args:
        app: Flask application instance
    """
    with app.app_context():
        try:
            reports_folder = app.config.get('REPORTS_FOLDER', 'reports')
            retention_days = app.config.get('FILE_RETENTION_DAYS', 90)
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            
            if not os.path.exists(reports_folder):
                return
            
            deleted_count = 0
            
            for filename in os.listdir(reports_folder):
                file_path = os.path.join(reports_folder, filename)
                
                try:
                    # Check file age
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                    
                    if file_mtime < cutoff_date:
                        os.remove(file_path)
                        deleted_count += 1
                        logger.debug(f"Deleted old report: {filename}")
                        
                except Exception as e:
                    logger.error(f"Error deleting report {filename}: {str(e)}")
                    continue
            
            logger.info(f"Report cleanup completed - Deleted: {deleted_count} files")
            
        except Exception as e:
            logger.error(f"Report cleanup failed: {str(e)}", exc_info=True)


def cleanup_temp_files(app):
    """
    Clean up temporary files from temp directory.
    
    Args:
        app: Flask application instance
    """
    import tempfile
    
    try:
        temp_dir = tempfile.gettempdir()
        creditbridge_temp_pattern = 'creditbridge_'
        
        deleted_count = 0
        cutoff_date = datetime.utcnow() - timedelta(hours=24)
        
        for filename in os.listdir(temp_dir):
            if filename.startswith(creditbridge_temp_pattern):
                file_path = os.path.join(temp_dir, filename)
                
                try:
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                    
                    if file_mtime < cutoff_date:
                        os.remove(file_path)
                        deleted_count += 1
                        
                except Exception as e:
                    logger.debug(f"Error deleting temp file {filename}: {str(e)}")
                    continue
        
        if deleted_count > 0:
            logger.info(f"Temp file cleanup completed - Deleted: {deleted_count} files")
            
    except Exception as e:
        logger.error(f"Temp file cleanup failed: {str(e)}")


def setup_cleanup_scheduler(app, db, DocumentUpload):
    """
    Set up scheduled cleanup tasks.
    
    Args:
        app: Flask application instance
        db: Database instance
        DocumentUpload: DocumentUpload model class
    """
    scheduler = BackgroundScheduler()
    
    # Schedule file cleanup - daily at 2 AM
    scheduler.add_job(
        func=lambda: cleanup_old_files(app, db, DocumentUpload),
        trigger=CronTrigger(hour=2, minute=0),
        id='cleanup_old_files',
        name='Clean up old uploaded files',
        replace_existing=True
    )
    
    # Schedule report cleanup - daily at 3 AM
    scheduler.add_job(
        func=lambda: cleanup_old_reports(app),
        trigger=CronTrigger(hour=3, minute=0),
        id='cleanup_old_reports',
        name='Clean up old PDF reports',
        replace_existing=True
    )
    
    # Schedule temp file cleanup - every 6 hours
    scheduler.add_job(
        func=lambda: cleanup_temp_files(app),
        trigger=CronTrigger(hour='*/6'),
        id='cleanup_temp_files',
        name='Clean up temporary files',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("Cleanup scheduler started")
    
    return scheduler


def manual_cleanup(app, db, DocumentUpload):
    """
    Manually trigger all cleanup tasks.
    
    Args:
        app: Flask application instance
        db: Database instance
        DocumentUpload: DocumentUpload model class
    """
    logger.info("Starting manual cleanup...")
    
    cleanup_old_files(app, db, DocumentUpload)
    cleanup_old_reports(app)
    cleanup_temp_files(app)
    
    logger.info("Manual cleanup completed")
