import asyncio
from uuid import UUID
import uuid
from typing import List, Dict, Any
from celery.utils.log import get_task_logger
from elasticsearch import AsyncElasticsearch

from config.elastic import INDEX_NAME
from rag.retriever import EmbeddingModel
from config.celery_config import celery_app

logger = get_task_logger(__name__)
_embed_model = None

async def _async_search(search_body):
    async_es = AsyncElasticsearch("http://elasticsearch:9200")
    try:
        return await async_es.search(index=INDEX_NAME, body=search_body)
    finally:
        await async_es.close()

async def _async_index(id, body):
    async_es = AsyncElasticsearch("http://elasticsearch:9200")
    try:
        await async_es.index(index=INDEX_NAME, id=str(id), body=body)
    finally:
        await async_es.close()

def get_embed_model():
    global _embed_model
    if _embed_model is None:
        _embed_model = EmbeddingModel()
    return _embed_model

@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    queue="gpu_queue",
    max_retries=3,
    acks_late=True,
)
def index_document_chunks(self, user_id: UUID, chat_id: UUID, document_id: UUID, chunk: str, chunk_index: int):
    model = get_embed_model()
    embeddings = model.embed([chunk]).tolist()

    try:
        body = {
            "user_id": str(user_id),
            "chat_id": str(chat_id),
            "document_id": str(document_id),
            "chunk_index": chunk_index,
            "text_content": chunk,
            "embedding": embeddings[0]
        }
        asyncio.run(_async_index(f"{document_id}_{chunk_index}", body))
    except Exception as e:
        raise e

@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    queue="gpu_queue",
    max_retries=3,
    acks_late=True,
)
def hybrid_search(self, user_id: UUID, chat_id: UUID, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    model = get_embed_model()
    logger.info(f"query: {query} with chat id: {chat_id}")
    query_vector = model.embed([query])[0].tolist()
    
    search_body = {
        "size": top_k,
        "knn": {
            "field": "embedding",
            "query_vector": query_vector,
            "k": top_k,
            "num_candidates": 1000,
            "filter": [
                {"term": {"chat_id": str(chat_id)}}
            ]
        },
        "query": {
            "bool": {
                "must": [
                    {
                        "match": {
                            "text_content": {
                                "query": query, 
                                "minimum_should_match": "20%"
                            }
                        }
                    }
                ],
                "filter": [
                    {"term": {"chat_id": str(chat_id)}}
                ]
            }
        },
        "_source": ["document_id", "chat_id", "chunk_index", "text_content"]
    }

    response = asyncio.run(_async_search(search_body))
    
    results = []
    for hit in response["hits"]["hits"]:
        results.append({
            "score": hit.get("_score"), 
            "document_id": hit["_source"]["document_id"],
            "chunk_index": hit["_source"]["chunk_index"],
            "text": hit["_source"]["text_content"]
        })

    return results