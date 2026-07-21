import os
from celery import Celery

celery_app = Celery(
    "rag_system",
    broker=os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672//"),
    backend="redis://localhost:6379/0"  
)

celery_app.conf.task_routes = {
    'tasks.cpu.*': {'queue': 'cpu_queue'},
    'tasks.gpu.*': {'queue': 'gpu_queue'},
}

celery_app.conf.update(
    task_acks_late=True,          
    worker_prefetch_multiplier=1, # Fair Scheduling 
    broker_connection_retry_on_startup = True
)