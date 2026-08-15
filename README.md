# Document Retrieval and QA

Document Retrieval and QA is a Django application for uploading DOCX files,
searching their contents, and answering questions from retrieved document text.
It stores documents and question history in SQLite and uses OpenRouter for text
embeddings and answer generation.

## Features

- Upload, list, update, and delete DOCX documents.
- Search indexed document passages using natural-language queries.
- Generate document-grounded answers and retain question history.
- Preserve source text and document metadata in search and answer results.

## Requirements

For Docker-based execution:

- Docker with the Compose plugin
- An OpenRouter API key

For local execution:

- Python 3.13
- An OpenRouter API key

## Configuration

Copy the example configuration and set `OPENROUTER_API_KEY`:

```sh
cp .env.example .env
```

The example values are suitable for local development. Available variables are:

| Variable | Description |
| --- | --- |
| `DJANGO_SECRET_KEY` | Django secret key. Replace the example value outside local development. |
| `DJANGO_DEBUG` | Enables Django debug mode. |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames accepted by Django. |
| `DJANGO_DB_PATH` | Path to the SQLite database file. |
| `DJANGO_TIME_ZONE` | Time zone used by Django. |
| `OPENROUTER_API_KEY` | OpenRouter credential used for embeddings and answer generation. |
| `OPENROUTER_MODEL` | OpenRouter model used to generate answers. |
| `OPENROUTER_EMBEDDING_MODEL` | OpenRouter model used to embed documents and queries. |
| `OPENROUTER_GENERATION_TIMEOUT` | Answer-generation timeout in seconds. |
| `OPENROUTER_EMBEDDING_TIMEOUT_MS` | Embedding-request timeout in milliseconds. |
| `OPENROUTER_EMBEDDING_RETRIES` | Number of retries for failed embedding requests. |
| `RAG_TOP_K` | Number of passages retrieved for each question. |
| `RAG_TEMPERATURE` | Generation temperature. |
| `RAG_MAX_TOKENS` | Maximum number of generated answer tokens. |
| `RAG_MAX_RETRIES` | Number of retries for failed generation requests. |
| `DOCUMENT_CHUNK_SIZE` | Maximum document chunk size in characters. |
| `DOCUMENT_CHUNK_OVERLAP` | Character overlap between adjacent chunks. |
| `CHROMA_PERSIST_DIRECTORY` | Directory used for the persistent Chroma index. |
| `CHROMA_COLLECTION_NAME` | Chroma collection used for document chunks. |

## Running with Docker

```sh
cp .env.example .env
# Set OPENROUTER_API_KEY in .env.
docker compose up --build
```

Compose applies database migrations automatically. The server listens at
<http://127.0.0.1:8000/>, with application APIs under `/api/`.

## Running Locally

### Linux and macOS

```sh
python3.13 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
# Set OPENROUTER_API_KEY in .env.
python manage.py migrate
python manage.py runserver
```

### Windows (PowerShell)

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Set OPENROUTER_API_KEY in .env.
python manage.py migrate
python manage.py runserver
```

The server listens at <http://127.0.0.1:8000/>, with application APIs under
`/api/`.

## Tests

```sh
python manage.py test
```

## API Documentation

See [docs/API.md](docs/API.md) for endpoint details and request examples.
