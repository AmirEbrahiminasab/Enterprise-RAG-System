# Enterprise RAG System

A production-ready **Retrieval-Augmented Generation (RAG)** backend built with FastAPI, Celery, Elasticsearch, and GPU-accelerated embeddings. Users upload documents into per-chat knowledge bases and query them through a streaming LLM-powered chat interface.

The companion TypeScript/Vite frontend ("Parallax UI") lives in [`ui/`](./ui/README.md).

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Data Flow](#data-flow)
  - [Document Ingestion](#document-ingestion)
  - [Query Processing](#query-processing)
- [API Reference](#api-reference)
- [Configuration & Environment Variables](#configuration--environment-variables)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Running with Docker Compose](#running-with-docker-compose)
  - [Running the API Locally](#running-the-api-locally)
  - [Running the Frontend](#running-the-frontend)
- [Worker Architecture](#worker-architecture)
- [Database Schema](#database-schema)
- [Elasticsearch Index](#elasticsearch-index)
- [Authentication](#authentication)
- [Testing](#testing)
- [License](#license)

---

## Architecture Overview

```mermaid
flowchart TD
    Browser["Parallax UI\n(TypeScript / Vite)"]
    API["FastAPI\nport 8585"]
    PG["PostgreSQL\nUsers · Chats · Docs · Messages"]
    MinIO["MinIO\nS3-compatible object store"]
    RMQ["RabbitMQ\nMessage Broker"]
    Redis["Redis\nCelery result backend"]
    CPU["CPU Worker\ncelery · cpu_queue"]
    GPU["GPU Worker\ncelery · gpu_queue · CUDA"]
    ES["Elasticsearch\nHybrid vector + BM25 index"]
    Router["RouterAgent\nnvidia/nemotron-nano (OpenRouter)"]
    Chat["ChatAgent\nnvidia/nemotron-ultra (OpenRouter)"]

    Browser -->|"REST + SSE stream"| API
    API --> PG
    API -->|"upload file"| MinIO
    API -->|"start_document_processing.delay()"| RMQ
    API -->|"start_query_processing (async generator)"| Router
    Router --> GPU
    GPU -->|"hybrid_search"| ES
    Router --> Chat
    Chat -->|"SSE chunks"| API
    RMQ --> CPU
    CPU -->|"extract & chunk"| GPU
    GPU -->|"embed + index"| ES
    CPU --> Redis
    GPU --> Redis
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI 0.116+, Uvicorn, Python 3.12 |
| Auth | JWT (HS256) via `python-jose`, bcrypt via `passlib` |
| Task Queue | Celery + RabbitMQ (broker) + Redis (result backend) |
| Databases | PostgreSQL 16 (async via `asyncpg` + SQLAlchemy 2) |
| Object Storage | MinIO (S3-compatible, accessed via `aioboto3`) |
| Vector Search | Elasticsearch 8.12 (dense vector KNN + BM25 hybrid) |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` on CUDA (bfloat16, SDPA) |
| LLM Routing | RouterAgent → `nvidia/nemotron-3-nano-omni-30b` (OpenRouter) |
| LLM Chat | ChatAgent → `nvidia/nemotron-3-ultra-550b` (OpenRouter, streaming) |
| Document Parsing | `pypdf` (PDF), built-in UTF-8 decode (TXT) |
| Text Splitting | LangChain `RecursiveCharacterTextSplitter` |
| Frontend | TypeScript, Vite 6, vanilla DOM (no framework) |

---

## Project Structure

```
Enterprise-RAG-System/
├── main.py                     # Uvicorn entry point (port 8585)
├── requirements.txt
├── Dockerfile                  # Python 3.12-slim + CUDA 12.4 PyTorch
├── docker-compose.yml          # Full infrastructure stack
│
├── apps/
│   ├── app.py                  # FastAPI application & all route handlers
│   ├── auth/
│   │   └── auth.py             # JWT creation/validation, password hashing, access guards
│   ├── chat/
│   │   ├── models.py           # RouterAgent and ChatAgent (OpenRouter API clients)
│   │   └── prompts.py          # System prompts for both agents
│   └── documents/
│       ├── preprocess.py       # Text extraction (PDF/TXT) and chunking
│       └── services.py         # Async DB helpers (CRUD for chat, message, document)
│
├── config/
│   ├── database.py             # SQLAlchemy ORM models + async engine setup
│   ├── elastic.py              # Elasticsearch client, index creation, chunk deletion
│   ├── s3.py                   # MinIO upload/download helpers
│   ├── celery_config.py        # Celery app config (broker, backend, routing)
│   └── schemas.py              # Pydantic request schemas
│
├── workers/
│   ├── cpu_worker.py           # Document processing pipeline + query orchestration
│   └── gpu_worker.py           # Embedding generation + hybrid search (GPU tasks)
│
├── rag/
│   └── retriever.py            # EmbeddingModel wrapper (all-MiniLM-L6-v2)
│
├── test/
│   └── test_elastic.py         # Manual hybrid search test against live Elasticsearch
│
└── ui/                         # Parallax UI (TypeScript/Vite) — see ui/README.md
```

---

## Data Flow

### Document Ingestion

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant MinIO
    participant DB as PostgreSQL
    participant CPU as CPU Worker
    participant GPU as GPU Worker (×N parallel)
    participant ES as Elasticsearch

    Client->>API: POST /chat/{id}/upload (PDF or TXT)
    API->>MinIO: upload_to_s3() → returns object_key
    API->>DB: INSERT Document (status=PENDING)
    API->>CPU: start_document_processing.delay()
    API-->>Client: 200 { document_id }

    CPU->>DB: status → PROCESSING
    CPU->>MinIO: read_from_s3(object_key)
    CPU->>CPU: extract text (pypdf / UTF-8)
    CPU->>CPU: RecursiveCharacterTextSplitter\n(chunk_size=1000, overlap=150)
    CPU->>GPU: chord of index_document_chunks tasks\n(batches of 4 chunks)

    GPU->>GPU: all-MiniLM-L6-v2.encode()\n(bfloat16 · SDPA · CUDA)
    GPU->>ES: bulk index {embedding, text_content,\nchat_id, document_id, chunk_index}

    CPU->>DB: status → COMPLETED (or FAILED + cleanup)
```

### Query Processing

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant Router as RouterAgent\n(nemotron-nano)
    participant GPU as GPU Workers (parallel)
    participant ES as Elasticsearch
    participant Chat as ChatAgent\n(nemotron-ultra)
    participant DB as PostgreSQL

    Client->>API: POST /chat/{id}/new_message
    API->>DB: INSERT user Message
    API->>DB: fetch chat history

    API->>Router: decompose query → JSON\n{ questions: [{ question, queries[] }] }

    loop per question
        Router->>GPU: group(hybrid_search.s()) for each query
        GPU->>ES: kNN (cosine) + BM25 match\nfiltered by chat_id
        GPU-->>Router: ranked hits
        Router->>Router: deduplicate, keep top-3 per question
    end

    API->>Chat: context + history → stream response
    Chat-->>API: SSE token chunks
    API-->>Client: StreamingResponse (text/event-stream)
    API->>DB: INSERT assistant Message (full answer)
```

---

## API Reference

All protected endpoints require `Authorization: Bearer <token>`.

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/signup` | — | Register a new user `{ name, email, password }` |
| `POST` | `/token` | — | OAuth2 password-form login → `{ access_token, token_type }` |
| `GET` | `/` | — | Health check |
| `POST` | `/new_chat` | ✓ | Create a new chat `{ title }` |
| `GET` | `/chat` | ✓ | List all chats for the authenticated user |
| `GET` | `/chat/{chat_id}` | ✓ | Fetch a single chat |
| `GET` | `/chat/{chat_id}/messages` | ✓ | Fetch all messages in a chat |
| `GET` | `/chat/{chat_id}/documents` | ✓ | List documents attached to a chat |
| `POST` | `/chat/{chat_id}/new_message` | ✓ | Send a message — returns **SSE stream** |
| `POST` | `/chat/{chat_id}/upload` | ✓ | Upload a `.pdf` or `.txt` file for indexing |

### Streaming Messages

`POST /chat/{chat_id}/new_message` returns `Content-Type: text/event-stream`. The response body is raw chunked text (not SSE `data:` framing); consume it with `ReadableStream` / `fetch` in the browser, or with `requests(stream=True)` in Python.

---

## Configuration & Environment Variables

Copy `.env.example` (or create `.env`) in the project root. Variables consumed by the application:

| Variable | Used In | Description |
|---|---|---|
| `SECRET_KEY_AUTH` | `apps/auth/auth.py` | Secret for signing JWT tokens |
| `Router_API` | `apps/chat/models.py` | OpenRouter API key for the RouterAgent |
| `Chat_API` | `apps/chat/models.py` | OpenRouter API key for the ChatAgent |
| `HTTPS_PROXY` / `HTTP_PROXY` | Docker Compose workers | Corporate proxy for outbound HTTPS |

> **Never commit `.env` to version control.** The `.gitignore` already excludes it.

Infrastructure service credentials (Postgres, MinIO, RabbitMQ, Redis) are hardcoded as dev defaults in `config/` files and `docker-compose.yml`. Change them for any non-local environment.

---

## Getting Started

### Prerequisites

- Docker & Docker Compose v2
- An NVIDIA GPU with CUDA 12.4+ drivers (required by the `gpu_worker` and `app` containers)
- [OpenRouter](https://openrouter.ai/) API keys for both agents
- `nvidia-container-toolkit` installed on the host for GPU passthrough

### Running with Docker Compose

```bash
# 1. Create your environment file
cp .env.example .env   # then fill in SECRET_KEY_AUTH, Router_API, Chat_API

# 2. (First run) Pre-download the embedding model so workers start offline
#    The model is cached to .cache/huggingface inside the repo root,
#    which is mounted into the containers at /app/.cache/huggingface.
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# 3. Start the full stack
docker compose up --build

# 4. Start the FastAPI server inside the app container
docker compose exec app python main.py
```

Services started by Docker Compose:

| Container | Port(s) | Description |
|---|---|---|
| `local_postgres` | 5432 | PostgreSQL 16 |
| `local_mongodb` | 27017 | MongoDB 7 (available, not yet used by app code) |
| `local_elasticsearch` | 9200, 9300 | Elasticsearch 8.12 |
| `local_rabbitmq` | 5672, 15672 | RabbitMQ + management UI |
| `local_redis` | 6379 | Redis 7.2 |
| `local_minio` | 9000, 9001 | MinIO + web console |
| `local_cpu_worker` | — | Celery worker on `cpu_queue` (concurrency 4) |
| `local_gpu_worker` | — | Celery worker on `gpu_queue` (concurrency 2, GPU) |
| `rag_app` | 8585 | App container (run API manually inside) |

### Running the API Locally

If you prefer to run the API outside Docker (infrastructure still via Compose):

```bash
pip install -r requirements.txt
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# Update service hostnames in config/ from Docker aliases to localhost,
# e.g. change "postgresql+asyncpg://dev_user:dev_password@local_postgres:5432/dev_database"
#       to   "postgresql+asyncpg://dev_user:dev_password@localhost:5432/dev_database"

python main.py
```

API will be available at `http://localhost:8585`. Interactive docs at `http://localhost:8585/docs`.

### Running the Frontend

See [`ui/README.md`](./ui/README.md) for full details.

```bash
cd ui
npm install
npm run dev        # http://localhost:5173 — proxies /api/* to :8585
```

---

## Worker Architecture

Celery is configured with two dedicated queues routed by task type:

```
RabbitMQ (amqp://rabbitmq:5672)
    ├── cpu_queue  →  cpu_worker  (concurrency=4)
    │       ├── tasks.cpu.start_document_processing  (main orchestrator, max_retries=3)
    │       ├── tasks.cpu.mark_document_completed
    │       └── tasks.cpu.handle_document_failure    (link_error callback)
    │
    └── gpu_queue  →  gpu_worker  (concurrency=2, GPU)
            ├── tasks.gpu.index_document_chunks      (parallel batch embed + ES index)
            └── tasks.gpu.hybrid_search              (embed query + kNN+BM25 search)
```

**Chord pattern for document processing:**

```
start_document_processing (CPU)
    └── chord([
            index_document_chunks.s(batch_0),  ← GPU
            index_document_chunks.s(batch_1),  ← GPU
            ...
        ])(
            mark_document_completed.s(document_id)        ← CPU (on success)
            .on_error(handle_document_failure.s(...))     ← CPU (on any failure)
        )
```

Redis stores Celery task results. `task_acks_late=True` and `worker_prefetch_multiplier=1` ensure fair scheduling and at-least-once delivery.

---

## Database Schema

Managed by SQLAlchemy auto-migration on startup (`Base.metadata.create_all`).

```
users
  id            UUID  PK
  name          TEXT
  email         TEXT  UNIQUE
  hashed_password TEXT
  created_at    TIMESTAMP

chats
  id            UUID  PK
  title         TEXT
  user_id       UUID  FK → users.id
  created_at    TIMESTAMP

documents
  id            UUID  PK
  title         TEXT
  path          TEXT  (MinIO object key)
  chat_id       UUID  FK → chats.id
  status        ENUM  pending | processing | completed | failed
  uploaded_at   TIMESTAMP

messages
  id            UUID  PK
  content       TEXT
  role          TEXT  (user | system)
  chat_id       UUID  FK → chats.id
  sent_at       TIMESTAMP
```

---

## Elasticsearch Index

Index name: **`rag`**

```json
{
  "user_id":     { "type": "keyword" },
  "chat_id":     { "type": "keyword" },
  "document_id": { "type": "keyword" },
  "chunk_index": { "type": "integer" },
  "text_content":{ "type": "text" },
  "embedding":   { "type": "dense_vector", "index": true, "similarity": "cosine" }
}
```

Retrieval uses **hybrid search**: approximate kNN (cosine similarity) combined with a BM25 `match` query, both filtered to the specific `chat_id`. Results are deduplicated and the top 3 chunks per question are passed to the LLM as context.

---

## Authentication

- Passwords hashed with **bcrypt** via `passlib`.
- Sessions use **JWT (HS256)** signed with `SECRET_KEY_AUTH`, expiring after **60 minutes**.
- All chat and document endpoints enforce ownership: a user can only access their own chats and documents. Attempting to access another user's chat returns `403 Forbidden`.

---

## Testing

`test/test_elastic.py` is a manual integration test that runs a hybrid search against a live Elasticsearch instance with a real query and a hardcoded `chat_id`. To run it (from inside the app container or with services reachable at `localhost`):

```bash
python -m test.test_elastic
```

---

## License

See [LICENSE](./LICENSE).
