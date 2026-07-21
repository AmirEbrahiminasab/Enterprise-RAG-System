import os
from celery import Celery

celery_app = Celery(
    "rag_system",
    broker="amqp://dev_user:dev_password@rabbitmq:5672//",
    backend="redis://redis:6379/0" ,
    include=['workers.cpu_document_worker', 'workers.gpu_document_worker']
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