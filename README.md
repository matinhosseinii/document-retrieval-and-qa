# Document Retrieval and QA

The project provides Django document management, persistent multilingual
semantic retrieval, and a simple two-step retrieve-then-generate RAG API. Day 3
uses the existing retriever as context for grounded answers through OpenRouter
and stores successful Q&A history in SQLite.

## Current capabilities

- SQLite-backed documents, DOCX validation/extraction, full REST CRUD, and Admin
- Unicode/Persian text preservation and file-replacement extraction
- LangChain recursive splitting (800 characters with 120 overlap)
- Normalized OpenRouter `nvidia/nemotron-3-embed-1b:free` embeddings
- Persistent Chroma index with deterministic chunk IDs and source metadata
- REST and Admin index synchronization on create, update, and delete
- Semantic search through `POST /api/search/`
- Grounded generation with LangChain's dedicated `ChatOpenRouter` integration
- SQLite-backed Q&A history and complete retrieved-context snapshots

## Setup

The Docker image targets Python 3.13, matching the tested local development
environment. Prerequisites are Python 3.13 for local setup or Docker with the
Compose plugin, plus an OpenRouter API key for real embedding and generation:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
# Edit .env and set OPENROUTER_API_KEY and other runtime configuration.
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

- Admin: <http://127.0.0.1:8000/admin/>
- Documents: <http://127.0.0.1:8000/api/documents/>
- Search: <http://127.0.0.1:8000/api/search/>
- Questions/history: <http://127.0.0.1:8000/api/questions/>

Django loads the project `.env` without overriding variables supplied by the
calling environment. `OPENROUTER_API_KEY` is shared by generation and
embeddings. `OPENROUTER_MODEL` selects the generation model, while
`OPENROUTER_EMBEDDING_MODEL` selects the embedding model. Document chunking,
RAG parameters, timeouts/retries, Django settings, and Chroma paths/names are
also configured in `.env`; see `.env.example` for the complete inventory.

Full endpoint contracts, response examples, and errors are documented in
[`docs/API.md`](docs/API.md).

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
contain original chunk `text`, `document_id`, `document_title`, `chunk_index`,
and `distance`. Distance is a vector-distance score, not a probability; lower
values represent nearer vectors within the configured embedding space.

The question endpoint validates one non-empty string, retrieves `RAG_TOP_K`
chunks (four by default),
formats them as delimited untrusted reference data, and invokes OpenRouter with
temperature `0.1`, at most 512 output tokens, and no client-level retries by
default. The
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
in the configured collection. Passage embeddings receive the
`passage:` prefix and query embeddings receive `query:`; neither prefix changes
returned text. Replacing a file computes all new embeddings before upserting the
replacement chunks and deleting obsolete old IDs, so an embedding-provider
failure leaves the previous usable index intact. A title-only update changes
Chroma metadata without re-embedding. Delete removes all records for the
document ID.

The OpenRouter embedding adapter and Chroma client are reused once per Django
process. Document chunks are embedded in batches, provider vectors are
validated and L2-normalized locally, and remote calls use bounded timeout/retry
settings.

Changing embedding models requires rebuilding into a separate Chroma collection
because vectors from different models must never be mixed. Set a new
`CHROMA_COLLECTION_NAME`, then run:

```sh
python manage.py rebuild_document_index
```

The command reports the target and expected counts, refuses a populated target,
and supports `--force` to clear only the configured target collection. It never
deletes unrelated collections. No rebuild runs automatically at startup.

## Tests

```sh
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

Tests use generated DOCX files, temporary storage, and deterministic test
embeddings, so they make no OpenRouter embedding requests or pollute
`data/chroma/`.

## Docker

```sh
cp .env.example .env
# Edit .env and set OPENROUTER_API_KEY and any desired model settings.
docker compose up --build
```

Container startup runs database migrations before starting Django's development
server. To use Admin, create a superuser separately:

```sh
docker compose run --rm web python manage.py createsuperuser
```

The `./data/chroma:/app/data/chroma` bind mount preserves the index across
container replacement. Compose passes the same project `.env` to the service;
no key is baked into the image.
SQLite and Django's development server remain in use; there is no Redis, task
worker, or external database. Startup does not create a superuser, load sample
data, or rebuild Chroma.

## Manual Persian retrieval and Q&A verification

Upload the intentional delivery sample:

```sh
curl -X POST http://127.0.0.1:8000/api/documents/ \
  -F 'title=گزارش شرکت آریا' \
  -F 'file=@sample_data/aria_company.docx'
```

Note the returned ID and vary `query` in the search request above. Both
`چند نفر در شرکت کار می‌کنند؟` and `نیروی انسانی مجموعه چند نفر است؟` should
rank the ۱۲۰-person fact near the top. `مقر اصلی شرکت کجاست؟` should rank the
Tehran fact; `شرکت چه نرم‌افزاری تولید می‌کند؟` the cloud HR system; and
`مدیرعامل چه کسی است؟` the Nastran Rezaei fact.

With a real OpenRouter key configured in `.env` and migrations applied, verify
the RAG workflow:

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

6. Failure: clear `OPENROUTER_API_KEY` (or temporarily use an invalid key) in
   `.env`,
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
- Embedding and answer generation depend on remote OpenRouter availability,
  latency, quotas, and model availability.
- SQLite is the source of truth and Chroma is derived state; they do not share a
  transaction. A failed replacement embedding can leave new SQLite content with
  the previous usable Chroma index until a retry or explicit rebuild.
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
