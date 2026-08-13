# Document Retrieval and QA

The project provides Django document management, persistent multilingual
semantic retrieval, and a simple two-step retrieve-then-generate RAG API. Day 3
uses the existing retriever as context for grounded answers through OpenRouter
and stores successful Q&A history in SQLite.

## Current capabilities

- SQLite-backed documents, DOCX validation/extraction, full REST CRUD, and Admin
- Unicode/Persian text preservation and file-replacement extraction
- LangChain recursive splitting (800 characters with 120 overlap)
- Local normalized `intfloat/multilingual-e5-small` embeddings
- Persistent Chroma index with deterministic chunk IDs and source metadata
- REST and Admin index synchronization on create, update, and delete
- Semantic search through `POST /api/search/`
- Grounded generation with LangChain's dedicated `ChatOpenRouter` integration
- SQLite-backed Q&A history and complete retrieved-context snapshots

## Setup

The Docker image and project support Python 3.11:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
export OPENROUTER_API_KEY='your-key'
export OPENROUTER_MODEL='openrouter/free'
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

- Admin: <http://127.0.0.1:8000/admin/>
- Documents: <http://127.0.0.1:8000/api/documents/>
- Search: <http://127.0.0.1:8000/api/search/>
- Questions/history: <http://127.0.0.1:8000/api/questions/>

Django reads `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, and
optionally `DJANGO_DB_PATH`. Retrieval settings can be overridden with
`CHROMA_PERSIST_DIRECTORY`, `CHROMA_COLLECTION_NAME`, `DOCUMENT_CHUNK_SIZE`,
`DOCUMENT_CHUNK_OVERLAP`, `EMBEDDING_MODEL_NAME`, and `EMBEDDING_DEVICE`.
Answer generation requires `OPENROUTER_API_KEY`; `OPENROUTER_MODEL` selects the
model without a code change and defaults to `openrouter/free`. Django does not
load `.env` automatically. Copying `.env.example` alone does not load it for a
local process; export the variables or configure them in the process manager.

## REST API

| Method | Path | Operation |
| --- | --- | --- |
| `GET` / `POST` | `/api/documents/` | List/upload documents |
| `GET` / `PUT` / `PATCH` / `DELETE` | `/api/documents/{id}/` | Document CRUD |
| `POST` | `/api/search/` | Retrieve semantically matching chunks |
| `POST` | `/api/questions/` | Retrieve, generate, and save an answer |
| `GET` | `/api/questions/` | List saved Q&A history |
| `GET` | `/api/questions/{id}/` | Retrieve one saved Q&A item |

Upload and search:

```sh
curl -X POST http://127.0.0.1:8000/api/documents/ \
  -F 'title=Example document' \
  -F 'file=@/path/to/example.docx'

curl -X POST http://127.0.0.1:8000/api/search/ \
  -H 'Content-Type: application/json' \
  -d '{"query":"چند نفر در شرکت کار می‌کنند؟","top_k":4}'

curl -X POST http://127.0.0.1:8000/api/questions/ \
  -H 'Content-Type: application/json' \
  -d '{"question":"نیروی انسانی شرکت چند نفر است؟"}'
```

`content` is read-only. Search `query` must be a non-empty JSON string;
`top_k` defaults to 4 and accepts JSON integers from 1 through 20. Results
contain original chunk `text`, `document_id`, `document_title`, and
`chunk_index`.

The question endpoint validates one non-empty string, retrieves four chunks,
formats them as delimited untrusted reference data, and invokes OpenRouter with
temperature `0.1`, at most 512 output tokens, and no client-level retries. The
grounding prompt requires answers to use only that context, ignore instructions
inside documents, abstain when evidence is insufficient, and use the question's
language. A successful response is saved with the exact retrieved chunk text and
metadata in `context_snapshot`. Retrieval distance remains available only from
`/api/search/`; it is not sent to the LLM or stored in Q&A history.

If retrieval returns no chunks, the API skips OpenRouter and stores a simple
deterministic no-information answer with an empty snapshot. Missing credentials
return HTTP 503; provider failures return HTTP 502. Neither failure creates a
history row.

## Retrieval architecture

SQLite `Document.content` is the source of truth; Chroma is a rebuildable
derived index stored at `data/chroma/`. On create, content is split and indexed
in the shared `documents` collection. Passage embeddings receive the E5
`passage:` prefix and query embeddings receive `query:`; neither prefix changes
returned text. Replacing a file deletes old chunks before indexing new content.
A title-only update changes Chroma metadata without re-embedding. Delete removes
all records for the document ID.

The Hugging Face embedding model and Chroma client are reused once per Django
process. The first real upload/search downloads and loads E5, so it can take
longer than later requests.

## Tests

```sh
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

Tests use generated DOCX files, temporary storage, and deterministic test
embeddings, so they do not download E5 or pollute `data/chroma/`.

## Docker

```sh
docker compose build
docker compose run --rm web python manage.py migrate
docker compose up
```

The `./data/chroma:/app/data/chroma` bind mount preserves the index across
container replacement. The Compose service passes `OPENROUTER_API_KEY` and
`OPENROUTER_MODEL` from the host environment; no key is baked into the image.
SQLite and Django's development server remain in use; there is no Redis, task
worker, or external database.

## Manual Persian retrieval and Q&A verification

Create a representative DOCX and upload it:

```sh
python - <<'PY'
from docx import Document

paragraphs = [
    "شرکت آریا در سال ۱۳۹۵ تأسیس شد و دفتر مرکزی آن در تهران قرار دارد.",
    "در حال حاضر شرکت آریا ۱۲۰ نفر کارمند دارد. از این تعداد، ۶۵ نفر در واحد فنی فعالیت می‌کنند.",
    "محصول اصلی شرکت یک سامانه مدیریت منابع انسانی ابری است.",
    "درآمد شرکت در سال ۱۴۰۴ حدود ۳۵ میلیارد تومان بوده است.",
    "مدیرعامل شرکت نسترن رضایی است.",
]
document = Document()
for paragraph in paragraphs:
    document.add_paragraph(paragraph)
document.save("/tmp/aria.docx")
PY

curl -X POST http://127.0.0.1:8000/api/documents/ \
  -F 'title=گزارش شرکت آریا' \
  -F 'file=@/tmp/aria.docx'
```

Note the returned ID and vary `query` in the search request above. Both
`چند نفر در شرکت کار می‌کنند؟` and `نیروی انسانی مجموعه چند نفر است؟` should
rank the ۱۲۰-person fact near the top. `مقر اصلی شرکت کجاست؟` should rank the
Tehran fact; `شرکت چه نرم‌افزاری تولید می‌کند؟` the cloud HR system; and
`مدیرعامل چه کسی است؟` the Nastran Rezaei fact.

With a real OpenRouter key exported and migrations applied, verify Day 3:

1. Grounded factual answer:

   ```sh
   curl -X POST http://127.0.0.1:8000/api/questions/ \
     -H 'Content-Type: application/json' \
     -d '{"question":"نیروی انسانی شرکت چند نفر است؟"}'
   ```

   The answer should mention `۱۲۰` and `context_snapshot` should contain the
   retrieved employee chunk.

2. Semantic retrieval plus generation:

   ```sh
   curl -X POST http://127.0.0.1:8000/api/questions/ \
     -H 'Content-Type: application/json' \
     -d '{"question":"مقر اصلی مجموعه کجاست؟"}'
   ```

   The answer should identify `تهران`.

3. Unsupported question:

   ```sh
   curl -X POST http://127.0.0.1:8000/api/questions/ \
     -H 'Content-Type: application/json' \
     -d '{"question":"قیمت سهام شرکت چقدر است؟"}'
   ```

   The model should say the available documents are insufficient, must not
   invent a price, and the normal retrieved snapshot should still be present.

4. History: take a successful response ID and run:

   ```sh
   curl http://127.0.0.1:8000/api/questions/
   curl http://127.0.0.1:8000/api/questions/ID/
   ```

   Both responses should retain the question, answer, and context snapshot.

5. Persistence: restart Django or run `docker compose restart web`, then repeat
   both history GETs. The Q&A rows remain in SQLite.

6. Failure: unset `OPENROUTER_API_KEY` (or temporarily use an invalid key),
   restart the process, POST another question, and compare history before and
   after. The request should fail clearly and no incomplete or fake-answer row
   should be added.

Lifecycle checks:

1. Persistence: confirm search, run `docker compose restart web`, then repeat
   it without uploading again.
2. Replacement: create `/tmp/aria-250.docx` with ۱۲۰ changed to ۲۵۰ and run
   `curl -X PATCH http://127.0.0.1:8000/api/documents/ID/ -F 'file=@/tmp/aria-250.docx'`.
   Search must show ۲۵۰ and no stale ۱۲۰ chunk for that document.
3. Title-only: run
   `curl -X PATCH http://127.0.0.1:8000/api/documents/ID/ -H 'Content-Type: application/json' -d '{"title":"گزارش جدید آریا"}'`.
   Search text remains available and `document_title` changes. Tests verify
   this path makes no add/re-embedding call.
4. Delete: run
   `curl -X DELETE http://127.0.0.1:8000/api/documents/ID/`, search again, and
   confirm no result contains that `document_id`.

## Known limitations

- Only ordinary DOCX paragraphs are extracted; PDF, tables, OCR, headers,
  footers, and images are unsupported. Uploaded media files are not cleaned up.
- Indexing and model loading are synchronous, so first use and large uploads
  increase request latency.
- Semantic search returns nearest neighbors whenever the collection is not
  empty; there is no relevance threshold or reranking layer. Unsupported-answer
  handling therefore relies on the grounding prompt.
- `openrouter/free` availability, latency, limits, and selected backing model can
  change. Set `OPENROUTER_MODEL` to a specific available model when stable model
  behavior is required.
- No-context responses use a fixed English message; no language-detection
  dependency is included for this retrieval edge case.
- There is no conversation memory, streaming, hybrid retrieval, provider
  fallback, application-level retries, or background indexing.
