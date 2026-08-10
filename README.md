# Document Retrieval and QA

Day 1 provides the document-management foundation for a Django-based document
question-answering project. It accepts DOCX uploads, extracts and stores their
complete paragraph text, and exposes document management through Django Admin
and a REST API.

RAG, LangChain, chunking, embeddings, vector search, OpenRouter, and question
answering are intentionally not implemented yet.

## Current capabilities

- SQLite-backed `Document` records with title, file, extracted content, and
  timestamps
- DOCX paragraph extraction with Unicode/Persian text preservation
- Clear validation errors for unsupported extensions and malformed DOCX files
- Django Admin create, view, search, edit, and delete workflows
- REST API list, create, retrieve, update, and delete operations
- Automatic re-extraction when an uploaded file is replaced
- Deterministic model, extraction, Admin, validation, and API tests

## Local setup

Python 3.13 is used by the development Docker image. Create a virtual
environment and install the dependencies:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

The application has development-safe defaults. For explicit local settings,
copy `.env.example` to `.env`, replace the example secret, then export its
values in your shell. Django reads `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`,
`DJANGO_ALLOWED_HOSTS`, and optionally `DJANGO_DB_PATH` from the environment;
it does not load `.env` files automatically.

Apply migrations and create an Admin user:

```sh
python manage.py migrate
python manage.py createsuperuser
```

Start the development server:

```sh
python manage.py runserver
```

- Admin: <http://127.0.0.1:8000/admin/>
- Document API: <http://127.0.0.1:8000/api/documents/>

## REST API

The router provides:

| Method | Path | Operation |
| --- | --- | --- |
| `GET` | `/api/documents/` | List documents |
| `POST` | `/api/documents/` | Upload a document |
| `GET` | `/api/documents/{id}/` | Retrieve a document |
| `PUT` / `PATCH` | `/api/documents/{id}/` | Update a document |
| `DELETE` | `/api/documents/{id}/` | Delete a document |

Upload a DOCX file as `multipart/form-data`:

```sh
curl -X POST http://127.0.0.1:8000/api/documents/ \
  -F 'title=Example document' \
  -F 'file=@/path/to/example.docx'
```

The `content` response field is read-only and is populated from the DOCX file.
Patching only `title` preserves the existing file and content. Supplying a new
`file` extracts and stores the replacement document's text.

## Media files

Uploaded files are stored under `media/documents/`. During development,
Django serves `MEDIA_URL` only when `DJANGO_DEBUG` is true. The `media/`
contents and the SQLite database are ignored by Git.

Deleting or replacing a database record does not currently remove its old file
from media storage; file lifecycle cleanup is deferred beyond the Day 1 scope.

## Tests and checks

```sh
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

Tests generate DOCX files in memory and use temporary media directories. They
do not require network access or machine-specific fixture paths.

## Docker development foundation

Build and start the single Django service:

```sh
docker compose build
docker compose run --rm web python manage.py migrate
docker compose up
```

This is deliberately a basic development container. It uses SQLite and the
Django development server; no database server, Redis, task worker, or reverse
proxy is included.

## Day 1 limitations

- Only normal DOCX paragraphs are extracted; tables, headers, footers, images,
  OCR, and PDF files are not processed.
- There is no authentication requirement on the REST API yet.
- There is no pagination or filtering beyond Admin title/content search.
- There is no asynchronous processing or production web-server configuration.
- There is no RAG, LangChain, embedding, vector-store, LLM, or QA functionality.
