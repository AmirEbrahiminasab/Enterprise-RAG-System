from celery_config import celery_app

@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    acks_late=True,
)
def embed_chunk(self, chunk_text: str, document_id: str, chat_id: str, chunk_index: int):
    # 1. Generate dense vector embedding via GPU TODO
    vector = embedding_model.encode(chunk_text)
    
    # 2. Index into ElasticSearch TODO
    es_client.index(
        index="rag_documents", 
        id=f"{document_id}_{chunk_index}", 
        body={"chat_id": chat_id, "text": chunk_text, "vector": vector}
    )
    return {"chunk_index": chunk_index, "status": "success"}