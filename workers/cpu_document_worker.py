import asyncio
from uuid import UUID

from celery import chord

from apps.documents.preprocess import extract_and_chunk_text
from apps.documents.services import update_document_status
from config.celery_config import celery_app
from config.database import DocumentStatus, WorkerSessionLocal
from workers.gpu_document_worker import hybrid_search, index_document_chunks


def _set_document_status(document_id: UUID, status: DocumentStatus) -> None:
    """Update a document's status from synchronous Celery task code.

    Opens a fresh session/connection (via `WorkerSessionLocal`, which uses
    NullPool) scoped to a single `asyncio.run()` call, so nothing is shared
    across event loops between task invocations.
    """

    async def _update():
        async with WorkerSessionLocal() as session:
            await update_document_status(session, document_id, status)

    asyncio.run(_update())


@celery_app.task(name="tasks.cpu.mark_document_completed")
def mark_document_completed(results, document_id: UUID):
    _set_document_status(document_id, DocumentStatus.COMPLETED)


@celery_app.task(name="tasks.cpu.handle_document_failure")
def handle_document_failure(request, exc, traceback, document_id: UUID):
    _set_document_status(document_id, DocumentStatus.FAILED)


@celery_app.task(
    bind=True,
    name="tasks.cpu.start_document_processing",
    max_retries=3,
    autoretry_for=(ConnectionError,),
    retry_backoff=True,
)
def start_document_processing(
    self, user_id: UUID, document_id: UUID, file_path: str, chat_id: UUID, filename: str
):
    _set_document_status(document_id, DocumentStatus.PROCESSING)

    chunks = extract_and_chunk_text(file_path, filename)

    parallel_tasks = [
        index_document_chunks.s(user_id, chat_id, document_id, chunk)
        for i, chunk in enumerate(chunks)
    ]

    chord(parallel_tasks)(mark_document_completed.s(document_id)).on_error(
        handle_document_failure.s(document_id)
    )
