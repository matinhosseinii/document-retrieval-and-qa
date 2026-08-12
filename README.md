# Document Retrieval and QA

Day 2 adds persistent multilingual semantic retrieval to the existing Django
DOCX document-management foundation. It indexes extracted content synchronously
and returns matching source chunks through REST. It does not generate answers
or call an LLM.

## Current capabilities

- SQLite-backed documents, DOCX validation/extraction, full REST CRUD, and Admin
- Unicode/Persian text preservation and file-replacement extraction
- LangChain recursive splitting (800 characters with 120 overlap)
- Local normalized `intfloat/multilingual-e5-small` embeddings
- Persistent Chroma index with deterministic chunk IDs and source metadata
- REST and Admin index synchronization on create, update, and delete
- Semantic search through `POST /api/search/`

## Setup

The Docker image and project support Python 3.11:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

- Admin: <http://127.0.0.1:8000/admin/>
- Documents: <http://127.0.0.1:8000/api/documents/>
- Search: <http://127.0.0.1:8000/api/search/>

Django reads `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, and
optionally `DJANGO_DB_PATH`. Retrieval settings can be overridden with
`CHROMA_PERSIST_DIRECTORY`, `CHROMA_COLLECTION_NAME`, `DOCUMENT_CHUNK_SIZE`,
`DOCUMENT_CHUNK_OVERLAP`, `EMBEDDING_MODEL_NAME`, and `EMBEDDING_DEVICE`.
Django does not load `.env` automatically.

## REST API

| Method | Path | Operation |
| --- | --- | --- |
| `GET` / `POST` | `/api/documents/` | List/upload documents |
| `GET` / `PUT` / `PATCH` / `DELETE` | `/api/documents/{id}/` | Document CRUD |
| `POST` | `/api/search/` | Retrieve semantically matching chunks |

Upload and search:

```sh
curl -X POST http://127.0.0.1:8000/api/documents/ \
  -F 'title=Example document' \
  -F 'file=@/path/to/example.docx'

curl -X POST http://127.0.0.1:8000/api/search/ \
  -H 'Content-Type: application/json' \
  -d '{"query":"چند نفر در شرکت کار می‌کنند؟","top_k":4}'
```

`content` is read-only. Search `query` must be a non-empty JSON string;
`top_k` defaults to 4 and accepts JSON integers from 1 through 20. Results
contain original chunk `text`, `document_id`, `document_title`, and
`chunk_index`.

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
container replacement. SQLite and Django's development server remain in use;
there is no Redis, task worker, external database, or API key.

## Manual Persian verification

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
  empty; there is no relevance threshold or LLM grounding decision yet.
- There is no answer generation, reranking, hybrid retrieval, or background
  indexing.
