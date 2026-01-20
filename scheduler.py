"""
Scheduled tasks for CreditBridge application.
Includes file cleanup, database maintenance, and other periodic tasks.
"""
import os
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger


def create_scheduler(app, db):
    """
    Create and configure background scheduler for periodic tasks.
    
    Args:
        app: Flask application instance
        db: SQLAlchemy database instance
        
    Returns:
        BackgroundScheduler: Configured scheduler
    """
    scheduler = BackgroundScheduler()
    
    # Import models inside function to avoid circular imports
    with app.app_context():
        from app import DocumentUpload, AuditLog
        
        def cleanup_old_files():
            """
            Clean up old uploaded files based on retention policy.
            Runs daily at 2 AM.
            """
            with app.app_context():
                try:
                    retention_days = app.config.get('FILE_RETENTION_DAYS', 90)
                    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
                    
                    # Find old documents
                    old_docs = DocumentUpload.query.filter(
                        DocumentUpload.uploaded_at < cutoff_date
                    ).all()
                    
                    deleted_count = 0
                    failed_count = 0
                    
                    for doc in old_docs:
                        try:
                            # Delete physical file
                            if os.path.exists(doc.file_path):
                                os.remove(doc.file_path)
                            
                            # Delete database record
                            db.session.delete(doc)
                            deleted_count += 1
                        except Exception as e:
                            app.logger.error(f"Failed to delete document {doc.id}: {str(e)}")
                            failed_count += 1
                            continue
                    
                    db.session.commit()
                    
                    app.logger.info(
                        f"File cleanup completed: {deleted_count} documents deleted, "
                        f"{failed_count} failed"
                    )
                    
                except Exception as e:
                    app.logger.error(f"File cleanup task failed: {str(e)}")
                    db.session.rollback()
        
        def cleanup_old_audit_logs():
            """
            Archive or delete old audit logs to prevent database bloat.
            Runs weekly on Sunday at 3 AM.
            """
            with app.app_context():
                try:
                    # Keep 1 year of audit logs
                    cutoff_date = datetime.utcnow() - timedelta(days=365)
                    
                    deleted_count = AuditLog.query.filter(
                        AuditLog.timestamp < cutoff_date
                    ).delete()
                    
                    db.session.commit()
                    
                    app.logger.info(f"Audit log cleanup: {deleted_count} old logs deleted")
                    
                except Exception as e:
                    app.logger.error(f"Audit log cleanup failed: {str(e)}")
                    db.session.rollback()
        
        def cleanup_orphaned_files():
            """
            Remove files from disk that don't have database records.
            Runs weekly on Saturday at 4 AM.
            """
            with app.app_context():
                try:
                    upload_folder = app.config.get('UPLOAD_FOLDER', 'uploads')
                    
                    if not os.path.exists(upload_folder):
                        return
                    
                    # Get all files in upload folder
                    disk_files = set()
                    for root, dirs, files in os.walk(upload_folder):
                        for file in files:
                            if file != '.gitkeep':
                                disk_files.add(os.path.join(root, file))
                    
                    # Get all file paths from database
                    db_files = set(
                        doc.file_path for doc in DocumentUpload.query.all()
                    )
                    
                    # Find orphaned files
                    orphaned = disk_files - db_files
                    
                    deleted_count = 0
                    for file_path in orphaned:
                        try:
                            os.remove(file_path)
                            deleted_count += 1
                        except Exception as e:
                            app.logger.error(f"Failed to delete orphaned file {file_path}: {str(e)}")
                    
                    app.logger.info(f"Orphaned files cleanup: {deleted_count} files deleted")
                    
                except Exception as e:
                    app.logger.error(f"Orphaned files cleanup failed: {str(e)}")
        
        def reset_daily_counters():
            """
            Reset daily counters for employees.
            Runs daily at midnight IST (00:00 Asia/Kolkata = 18:30 UTC previous day).
            
            This is a critical job for analytics accuracy.
            """
            with app.app_context():
                try:
                    from app import Employee, AuditLog
                    from datetime import datetime
                    
                    # Get count before reset for audit
                    active_employees = Employee.query.filter(
                        Employee.daily_assessment_count > 0
                    ).count()
                    
                    # Reset all counters in a single atomic query
                    affected = Employee.query.update({'daily_assessment_count': 0})
                    
                    # Log the reset action
                    AuditLog.log(
                        employee_id=None,  # System action
                        action='DAILY_RESET',
                        entity_type='system',
                        details={
                            'task': 'reset_daily_counters',
                            'employees_with_counts': active_employees,
                            'total_reset': affected,
                            'timestamp_utc': datetime.utcnow().isoformat()
                        }
                    )
                    
                    db.session.commit()
                    
                    app.logger.info(
                        f"Daily counters reset: {active_employees} employees had counts, "
                        f"{affected} total reset"
                    )
                    
                except Exception as e:
                    app.logger.error(f"Daily counter reset failed: {str(e)}")
                    db.session.rollback()
                    raise  # Re-raise for APScheduler to log
        
        def generate_daily_summary():
            """
            Generate and log daily summary statistics.
            Runs daily at 11 PM.
            """
            with app.app_context():
                try:
                    from app import CreditAssessment
                    
                    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                    
                    # Count today's assessments
                    total_today = CreditAssessment.query.filter(
                        CreditAssessment.assessment_date >= today
                    ).count()
                    
                    approved_today = CreditAssessment.query.filter(
                        CreditAssessment.assessment_date >= today,
                        CreditAssessment.status == 'approved'
                    ).count()
                    
                    pending_total = CreditAssessment.query.filter(
                        CreditAssessment.status.in_([
                            'draft', 'pending_review', 'under_review', 
                            'reviewed', 'pending_approval'
                        ])
                    ).count()
                    
                    app.logger.info(
                        f"DAILY SUMMARY: {total_today} assessments created, "
                        f"{approved_today} approved, {pending_total} pending"
                    )
                    
                except Exception as e:
                    app.logger.error(f"Daily summary generation failed: {str(e)}")
        
        # Schedule tasks
        
        # Daily file cleanup at 2 AM
        scheduler.add_job(
            func=cleanup_old_files,
            trigger=CronTrigger(hour=2, minute=0),
            id='cleanup_old_files',
            name='Clean up old uploaded files',
            replace_existing=True
        )
        
        # Weekly audit log cleanup (Sunday 3 AM)
        scheduler.add_job(
            func=cleanup_old_audit_logs,
            trigger=CronTrigger(day_of_week='sun', hour=3, minute=0),
            id='cleanup_audit_logs',
            name='Clean up old audit logs',
            replace_existing=True
        )
        
        # Weekly orphaned files cleanup (Saturday 4 AM)
        scheduler.add_job(
            func=cleanup_orphaned_files,
            trigger=CronTrigger(day_of_week='sat', hour=4, minute=0),
            id='cleanup_orphaned_files',
            name='Clean up orphaned files',
            replace_existing=True
        )
        
        # Daily counter reset at midnight
        scheduler.add_job(
            func=reset_daily_counters,
            trigger=CronTrigger(hour=0, minute=0),
            id='reset_daily_counters',
            name='Reset daily employee counters',
            replace_existing=True
        )
        
        # Daily summary at 11 PM
        scheduler.add_job(
            func=generate_daily_summary,
            trigger=CronTrigger(hour=23, minute=0),
            id='daily_summary',
            name='Generate daily summary',
            replace_existing=True
        )
        
        # ==========================================
        # ML OPS: Weekly Model Retraining
        # ==========================================
        
        def check_drift_and_retrain():
            """
            Check for data drift and retrain model if needed.
            Runs weekly on Sunday at 2 AM.
            """
            with app.app_context():
                try:
                    from ml_ops.monitoring.drift_detector import DriftDetector
                    from ml_ops.training.pipeline import TrainingPipeline
                    from ml_ops.registry.model_registry import ModelRegistry
                    from ml_ops.data.loader import DataLoader
                    from ml_ops.config import config
                    
                    app.logger.info("Starting weekly drift check and retrain job...")
                    
                    # Check if we have a baseline
                    detector = DriftDetector(config.baseline_path)
                    
                    if detector.baseline is None:
                        app.logger.info("No baseline found, skipping drift check")
                        return
                    
                    # Load recent production data
                    loader = DataLoader(config)
                    try:
                        production_df = loader.load_from_database(
                            limit=config.drift_check_sample_size
                        )
                    except Exception as e:
                        app.logger.warning(f"Could not load production data: {e}")
                        return
                    
                    if len(production_df) < 100:
                        app.logger.info("Insufficient production data for drift check")
                        return
                    
                    # Check for drift
                    drift_result = detector.detect_from_dataframe(
                        production_df, config.feature_names
                    )
                    
                    app.logger.info(f"Drift check result: {drift_result.summary()}")
                    
                    # Retrain if drift detected
                    if drift_result.overall_drift:
                        app.logger.info("Drift detected! Starting automatic retraining...")
                        
                        pipeline = TrainingPipeline(config)
                        result = pipeline.train(
                            dataset_version='latest',
                            generate_if_missing=True
                        )
                        
                        # Register new model
                        registry = ModelRegistry(config.registry_path, config.active_path)
                        version = registry.register(
                            model=result.model,
                            scaler=result.scaler,
                            metrics=result.metrics,
                            dataset_version=result.dataset_version,
                            hyperparameters=result.hyperparameters,
                            description="Auto-retrained due to drift detection"
                        )
                        
                        # Auto-activate if better
                        if config.auto_activate_on_improvement:
                            activated = registry.auto_activate_if_better(version)
                            if activated:
                                app.logger.info(f"Auto-activated new model {version}")
                            else:
                                app.logger.info(f"Kept previous model (new {version} not better)")
                        
                        app.logger.info(f"Retraining completed: {version}")
                    else:
                        app.logger.info("No significant drift detected, skipping retrain")
                        
                except Exception as e:
                    app.logger.error(f"ML retraining job failed: {str(e)}")
        
        # Weekly drift check and retrain (Sunday 2 AM)
        scheduler.add_job(
            func=check_drift_and_retrain,
            trigger=CronTrigger(day_of_week='sun', hour=2, minute=0),
            id='ml_drift_check_retrain',
            name='ML drift check and retrain',
            replace_existing=True
        )
        
        app.logger.info("Background scheduler initialized with 6 tasks (including ML retraining)")
    
    return scheduler


def start_scheduler(scheduler):
    """
    Start the background scheduler.
    
    Args:
        scheduler: BackgroundScheduler instance
    """
    if not scheduler.running:
        scheduler.start()
