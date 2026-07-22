import asyncio
import json
from uuid import UUID

from celery import chord, group

from apps.documents.preprocess import extract_and_chunk_text
from apps.documents.services import update_document_status, get_chat_history, create_message
from apps.chat.prompts import ROUTER_SYSTEM_PROMPT, CHAT_SYSTEM_PROMPT
from config.celery_config import celery_app
from config.database import DocumentStatus, WorkerSessionLocal
from apps.chat.models import ChatAgent, RouterAgent
from workers.gpu_worker import hybrid_search, index_document_chunks


def _set_document_status(document_id: UUID, status: DocumentStatus) -> None:
    async def _update():
        async with WorkerSessionLocal() as session:
            await update_document_status(session, document_id, status)

    asyncio.run(_update())

def _router_call(query: str, history: list):
    router = RouterAgent(ROUTER_SYSTEM_PROMPT)
    response = router.run(query, history)
    try:
        parsed = json.loads(response)
        return parsed.get("questions", [])
    except json.JSONDecodeError:
        return []

def _call_queries(questions_data: list, user_id: UUID, chat_id: UUID):
    all_docs = []
    
    for item in questions_data:
        queries = item.get("queries", [])
        if not queries:
            continue
            
        job = group(hybrid_search.s(user_id, chat_id, q) for q in queries)
        task_results = job.apply_async().get() 

        question_docs = []
        seen_chunks = set()
        
        for query_hits in task_results:
            for hit in query_hits:
                doc_key = f"{hit['document_id']}_{hit['chunk_index']}"
                if doc_key not in seen_chunks:
                    seen_chunks.add(doc_key)
                    question_docs.append(hit)

        question_docs.sort(key=lambda x: x['score'], reverse=True)
        top_3 = question_docs[:3]

        all_docs.append({
            "question": item.get("question"),
            "docs": [doc['text'] for doc in top_3]
        })
        
    return all_docs

def _llm_call(questions_docs: list, history: list, user_query: str):
    llm = ChatAgent(CHAT_SYSTEM_PROMPT)
    
    context_str = ""
    for item in questions_docs:
        context_str += f"\nQuestion: {item['question']}\nRelevant Context:\n"
        for i, doc in enumerate(item['docs']):
            context_str += f"[{i+1}] {doc}\n"
            
    user_prompt = f"Context Information:\n{context_str}\n\nPlease answer each user question utilizing their relevant context"
    
    return llm.run(user_prompt, history)


async def start_query_processing(user_id: UUID, content: str, chat_id: UUID):
    async with WorkerSessionLocal() as session:
        history_gen = get_chat_history(session, chat_id)
        history = await anext(history_gen, [])

    questions_data = await asyncio.to_thread(_router_call, content, history)
    if not questions_data:
        yield "I couldn't generate a strategy to answer that query."
        return

    questions_docs = await asyncio.to_thread(_call_queries, questions_data, user_id, chat_id)

    full_answer = ""
    llm_gen = _llm_call(questions_docs, history, content)

    def get_next_chunk():
        try:
            return next(llm_gen)
        except StopIteration:
            return None

    while True:
        chunk = await asyncio.to_thread(get_next_chunk)
        if chunk is None:
            break
        full_answer += chunk
        yield chunk

    async with WorkerSessionLocal() as session:
        await create_message(session, content=full_answer, role="system", chat_id=chat_id)


@celery_app.task(name="tasks.cpu.mark_document_completed", queue="cpu_queue")
def mark_document_completed(results, document_id: UUID):
    _set_document_status(document_id, DocumentStatus.COMPLETED)


@celery_app.task(name="tasks.cpu.handle_document_failure", queue="cpu_queue")
def handle_document_failure( document_id: UUID, request, exc, traceback):
    _set_document_status(document_id, DocumentStatus.FAILED)


@celery_app.task(
    bind=True,
    name="tasks.cpu.start_document_processing",
    max_retries=3,
    autoretry_for=(ConnectionError,),
    retry_backoff=True,
)
def start_document_processing(self, user_id: UUID, document_id: UUID, file_path: str, chat_id: UUID, filename: str):
    _set_document_status(document_id, DocumentStatus.PROCESSING)

    chunks = extract_and_chunk_text(file_path, filename)

    parallel_tasks = [
        index_document_chunks.s(user_id, chat_id, document_id, chunk, i)
        for i, chunk in enumerate(chunks)
    ]

    body_signature = mark_document_completed.s(document_id).on_error(
        handle_document_failure.s(document_id)
    )

    chord(parallel_tasks)(body_signature)
