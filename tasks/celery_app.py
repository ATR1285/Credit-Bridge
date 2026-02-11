"""
Celery Configuration for CreditBridge

Task queue for background PDF generation and other async operations.
Uses Redis as broker and result backend.
"""
from celery import Celery
import os

# Redis connection (Docker: redis://localhost:6379/0)
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')


def make_celery(app_name='creditbridge'):
    """
    Create and configure Celery instance.
    
    Args:
        app_name: Name for the Celery application
        
    Returns:
        Configured Celery instance
    """
    celery = Celery(
        app_name,
        broker=REDIS_URL,
        backend=REDIS_URL,
        include=['tasks.pdf_tasks']  # Auto-discover tasks
    )
    
    celery.conf.update(
        # Serialization
        task_serializer='json',
        result_serializer='json',
        accept_content=['json'],
        
        # Timezone
        timezone='Asia/Kolkata',
        enable_utc=True,
        
        # Task tracking
        task_track_started=True,
        result_extended=True,
        
        # Timeouts (PDF generation can take time)
        task_time_limit=180,  # 3 min hard limit
        task_soft_time_limit=120,  # 2 min soft limit
        
        # Reliability
        task_acks_late=True,  # Acknowledge after completion
        task_reject_on_worker_lost=True,
        
        # Performance (for Windows compatibility)
        worker_prefetch_multiplier=1,
        
        # Retry policy
        task_default_retry_delay=10,
        task_max_retries=3,
        
        # Result expiration (keep results for 24 hours)
        result_expires=86400,
    )
    
    return celery


# Global Celery instance
celery = make_celery()


class CeleryContextTask(celery.Task):
    """
    Base task that provides Flask app context.
    
    Inherit from this for tasks that need database access.
    """
    _app = None
    
    @property
    def app(self):
        if self._app is None:
            from app import app
            self._app = app
        return self._app
    
    def __call__(self, *args, **kwargs):
        with self.app.app_context():
            return super().__call__(*args, **kwargs)


# Set as default base class
celery.Task = CeleryContextTask
