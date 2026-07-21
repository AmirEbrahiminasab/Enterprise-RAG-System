from elasticsearch import Elasticsearch
from typing import List, Dict, Any
from uuid import UUID

es = Elasticsearch("http://localhost:9200")

INDEX_NAME = "rag"

async def create_elastic_index():
    if not es.indices.exists(index=INDEX_NAME):
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
                        "dims": 2048,
                        "index": True,
                        "similarity": "cosine" 
                    }
                }
            }
        }
        es.indices.create(index=INDEX_NAME, body=mapping)