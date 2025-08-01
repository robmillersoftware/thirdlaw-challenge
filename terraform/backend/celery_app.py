"""
Celery configuration for asynchronous PDF processing.
Provides background task processing for high-throughput scenarios.
"""

import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

# Celery configuration
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', REDIS_URL)

# Create Celery app
celery_app = Celery(
    'pdf_processor',
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=['backend.celery_tasks']
)

# Celery configuration
celery_app.conf.update(
    # Task routing
    task_routes={
        'backend.celery_tasks.process_pdf_async': {'queue': 'pdf_processing'},
        'backend.celery_tasks.process_pdf_scan_redact_async': {'queue': 'pdf_processing'},
    },
    
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Worker settings
    worker_prefetch_multiplier=1,  # Process one task at a time per worker
    task_acks_late=True,  # Acknowledge task only after completion
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks to prevent memory leaks
    
    # Result settings
    result_expires=3600,  # Results expire after 1 hour
    
    # Task time limits
    task_soft_time_limit=300,  # 5 minute soft limit
    task_time_limit=360,  # 6 minute hard limit
    
    # Concurrency settings
    worker_concurrency=min(8, (os.cpu_count() or 1) * 2),
    
    # Queue settings
    task_default_queue='pdf_processing',
    task_default_exchange='pdf_processing',
    task_default_exchange_type='direct',
    task_default_routing_key='pdf_processing',
)

if __name__ == '__main__':
    celery_app.start()