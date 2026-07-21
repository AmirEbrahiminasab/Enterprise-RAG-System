from .celery_config import celery_app
from uuid import UUID
from typing import List, Dict, Any
from config.elastic import es, INDEX_NAME

from rag.retriever import EmbeddingModel

embed_model = EmbeddingModel()

@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    acks_late=True,
)
def index_document_chunks(user_id: UUID, chat_id: UUID, document_id: UUID, chunks: List[str]):
    embeddings = embed_model.embed_document(chunks).tolist()
    
    operations = []
    for i, (chunk, vector) in enumerate(zip(chunks, embeddings)):
        action = {"index": {"_index": INDEX_NAME}}
        doc = {
            "user_id": str(user_id),
            "chat_id": str(chat_id),
            "document_id": str(document_id),
            "chunk_index": i,
            "text_content": chunk,
            "embedding": vector
        }
        operations.append(action)
        operations.append(doc)
        
    if operations:
        response = es.bulk(operations=operations)
        if response.get("errors"):
            print("Errors occurred during bulk indexing.")
            raise Exception(f"Bulk indexing failed.\n{response}")

@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    acks_late=True,
)
def hybrid_search(user_id: UUID, chat_id: UUID, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    query_vector = embed_model.embed_query([query])[0].tolist()
    
    search_body = {
        "size": top_k,
        "knn": {
            "field": "embedding",
            "query_vector": query_vector,
            "k": top_k,
            "num_candidates": 1000,
            "filter": [
                {"term": {"user_id": str(user_id)}},
                {"term": {"chat_id": str(chat_id)}}
            ]
        },
        "query": {
            "bool": {
                "must": [
                    {"match": {"text_content": query, "minimum_should_match": "20%"}}
                ],
                "filter": [
                    {"term": {"user_id": str(user_id)}},
                    {"term": {"chat_id": str(chat_id)}}
                ]
            }
        },
        "rank": {
            "rrf": {}
        },
        "_source": ["document_id", "chunk_index", "text_content"]
    }

    response = es.search(index=INDEX_NAME, body=search_body)
    
    results = []
    for hit in response["hits"]["hits"]:
        results.append({
            "score": hit.get("_score"), 
            "document_id": hit["_source"]["document_id"],
            "chunk_index": hit["_source"]["chunk_index"],
            "text": hit["_source"]["text_content"]
        })
        
    return results