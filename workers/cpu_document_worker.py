from .celery_config import celery_app
from celery import chord
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from config.database import DocumentStatus 
from apps.documents.preprocess import extract_and_chunk_text
from apps.documents.services import update_document_status
from .gpu_document_worker import index_document_chunks, hybrid_search


@celery_app.task(name="tasks.cpu.mark_document_completed")
def mark_document_completed(session: AsyncSession, results, document_id: UUID):
    update_document_status(session, document_id, DocumentStatus.COMPLETED) 

@celery_app.task(name="tasks.cpu.handle_document_failure")
def handle_document_failure(session: AsyncSession, request, exc, traceback, document_id: UUID):
    update_document_status(session, document_id, DocumentStatus.FAILED) 


@celery_app.task(bind=True, name="tasks.cpu.start_document_processing", max_retries=3, autoretry_for=(ConnectionError,), retry_backoff=True)
def start_document_processing(self, session: AsyncSession, user_id: UUID, document_id: UUID, file_path: str, chat_id: UUID):
    update_document_status(session, document_id, DocumentStatus.PROCESSING) 
    
    chunks = extract_and_chunk_text(file_path)
        
    parallel_tasks = [
        index_document_chunks.s(user_id, chat_id, document_id, chunk)
        for i, chunk in enumerate(chunks)
    ]
    
    chord(parallel_tasks)(
        mark_document_completed.s(session, document_id)
    ).on_error(handle_document_failure.s(session, document_id))    