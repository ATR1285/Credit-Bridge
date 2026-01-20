"""
Celery Worker Entry Point

Start with: celery -A celery_worker worker --loglevel=info --pool=solo

On Windows, use --pool=solo or --pool=threads
"""
import os
import sys

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import Celery app
from tasks.celery_app import celery

# Import tasks to register them
from tasks import pdf_tasks

# Make app available at module level for celery command
app = celery

if __name__ == '__main__':
    celery.start()
