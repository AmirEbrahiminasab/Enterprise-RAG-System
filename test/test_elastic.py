from elasticsearch import AsyncElasticsearch
from rag.retriever import EmbeddingModel
import asyncio

async def _async_search(search_body):
    async_es = AsyncElasticsearch("http://elasticsearch:9200")
    try:
        return await async_es.search(index=INDEX_NAME, body=search_body)
    finally:
        await async_es.close()

async def _async_get(document_id):
    async_es = AsyncElasticsearch("http://elasticsearch:9200")
    try:
        return await async_es.get(index=INDEX_NAME, id=str(document_id))
    finally:
        await async_es.close()

async def _async_count(index="_all"):
    async_es = AsyncElasticsearch("http://elasticsearch:9200")
    try:
        return await async_es.count(index=index)
    finally:    
        await async_es.close()


INDEX_NAME = "rag"

def main(query: str, chat_id: str):
    model = EmbeddingModel()
    query_vector = model.embed([query])[0].tolist()
    
    search_body = {
        "size": 2,
        "knn": {
            "field": "embedding",
            "query_vector": query_vector,
            "k": 2,
            "num_candidates": 1000,
            "filter": [
                        {"term": {"chat_id": chat_id}}
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
                    {"term": {"chat_id": chat_id}}
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

    print(results)

main("what are the references they used for their introduction to multi morbidity system and also what is the definition of multimorbidity?", "572269f6-f7b0-4074-baac-be4d5a8e3f46")
