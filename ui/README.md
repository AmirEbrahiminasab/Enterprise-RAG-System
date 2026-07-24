# Parallax UI

A standalone TypeScript/Vite interface for the Enterprise RAG API. All frontend source lives in this directory.

## Run locally

Start the FastAPI service on port `8585`, then:

```bash
cd ui
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api/*` to `http://localhost:8585`, so the backend does not need CORS changes.

## Production build

```bash
npm run build
```

Build output is written to `ui/dist`. If the built UI is served from a different origin than FastAPI, set `VITE_API_BASE_URL` to the API origin at build time and enable that origin in the backend's CORS policy. If both are reverse-proxied under one origin, route `/api/*` to FastAPI and no environment variable is needed.

## API behavior handled

- OAuth2 password-form login and JSON signup
- Bearer-authenticated chat/history/document requests
- Raw chunked message streaming via `fetch` and `ReadableStream`
- PDF/TXT uploads and async document processing statuses
- Empty API collections represented by backend `404` responses
