# Ry-Vector

Ry-Vector is a multi-user RAG application built with Streamlit, SQLite, Qdrant, and configurable OpenAI or Ollama models.

Users can register, upload documents, embed chunks into isolated per-user Qdrant collections, search with dynamic top-K retrieval, and chat with citations over their own documents.

## Features

- Register, login, logout with bcrypt password hashing.
- Per-user SQLite ownership for documents, chat sessions, and messages.
- Per-user Qdrant collections named `user_{user_id}`.
- Upload and process PDF, DOCX, XLSX, Markdown, and TXT files.
- Configurable chunk size, overlap, provider, models, default top-K, and streaming.
- Search UI with exact requested top-K limit and optional document filters.
- RAG chat with stored history, document scope selection, streaming toggle, citations, and JSON export.
- Delete documents and remove their vectors.
- Docker Compose setup for Streamlit, Qdrant, SQLite volume, and Ollama.

## Project Structure

```text
app/
  main.py
  auth/
  db/
  rag/
  vectorstore/
  llm/
  utils/
  models/
docker/
  Dockerfile
  docker-compose.yml
docker-compose.yml
.env.example
requirements.txt
```

## Quick Start With Docker

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Choose your provider in `.env`.

For OpenAI:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_key_here
CHAT_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
```

For Ollama:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_CHAT_MODEL=llama3
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
```

3. Start the stack from the repository root:

```bash
docker compose up --build
```

4. Open Streamlit:

```text
http://localhost:8501
```

5. Register a user, upload documents, then use Search or Chat.

## Ollama Model Setup

The compose file includes an Ollama service. After the containers are running, pull the models you configured:

```bash
docker compose exec ollama ollama pull llama3
docker compose exec ollama ollama pull nomic-embed-text
```

Then use `LLM_PROVIDER=ollama` in `.env` and restart the app container:

```bash
docker compose restart app
```

## Local Development

Use this only if you want to run outside Docker. You still need Qdrant and, if selected, Ollama running separately.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
streamlit run app/main.py
```

For local non-Docker Ollama, set:

```env
OLLAMA_BASE_URL=http://localhost:11434
QDRANT_HOST=localhost
```

## Environment Variables

```env
LLM_PROVIDER=openai|ollama
OPENAI_API_KEY=
OPENAI_BASE_URL=
CHAT_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_CHAT_MODEL=llama3
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
CHUNK_SIZE=800
CHUNK_OVERLAP=120
TOP_K_DEFAULT=5
STREAMING_ENABLED=true
SQLITE_PATH=./data/app.db
QDRANT_HOST=qdrant
QDRANT_PORT=6333
QDRANT_COLLECTION_PREFIX=user_
```

## Data Persistence

Docker volumes:

- `sqlite_data`: SQLite database and uploaded files under `/app/data`.
- `qdrant_storage`: Qdrant vector data.
- `ollama_models`: Ollama model cache.

SQLite tables are created automatically on app startup:

- `users`
- `documents`
- `chat_sessions`
- `chat_messages`

## Security Model

Ry-Vector enforces user isolation in two layers:

- SQLite queries always filter documents, sessions, and messages by `user_id`.
- Qdrant stores vectors in per-user collections named with `QDRANT_COLLECTION_PREFIX`, for example `user_1`.

Search and chat document filters are validated against SQLite ownership before Qdrant retrieval.

## Notes

- The app does not include hardcoded secrets. Configure provider credentials in `.env`.
- OpenAI mode requires `OPENAI_API_KEY` before uploading, searching, or chatting.
- Ollama mode requires the configured chat and embedding models to be pulled into the Ollama container.
- If you change embedding models after documents are indexed, use a new user account or clear the matching Qdrant collection, because vector dimensions must remain consistent per collection.

