from elasticsearch import AsyncElasticsearch
from typing import List, Dict, Any
from uuid import UUID

es = AsyncElasticsearch("http://elasticsearch:9200")

INDEX_NAME = "rag"

async def create_elastic_index():
    if not await es.indices.exists(index=INDEX_NAME):
        mapping = {
            "mappings": {
                "properties": {
                    "user_id": {"type": "keyword"},
                    "chat_id": {"type": "keyword"},
                    "document_id": {"type": "keyword"},
                    
                    "chunk_index": {"type": "integer"},
                    
                    "text_content": {"type": "text"},
                    
                    "embedding": {
                        "type": "dense_vector",
                        "index": True,
                        "similarity": "cosine" 
                    }
                }
            }
        }
        await es.indices.create(index=INDEX_NAME, body=mapping)