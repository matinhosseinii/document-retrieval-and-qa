# REST API

The API is available below `/api/` and currently requires no authentication.
JSON examples use `http://127.0.0.1:8000` as the base URL.

## Common representations

A Document response contains:

```json
{
  "id": 1,
  "title": "گزارش شرکت آریا",
  "file": "http://127.0.0.1:8000/media/documents/aria_company.docx",
  "content": "شرکت آریا در سال ۱۳۹۵ تأسیس شد.",
  "created_at": "2026-08-13T12:00:00+03:30",
  "updated_at": "2026-08-13T12:00:00+03:30"
}
```

`content`, `id`, `created_at`, and `updated_at` are read-only. The exact `file`
URL and timestamps depend on the request and server configuration.

A QuestionAnswer response contains:

```json
{
  "id": 1,
  "question": "نیروی انسانی شرکت چند نفر است؟",
  "answer": "شرکت آریا ۱۲۰ نفر کارمند دارد.",
  "context_snapshot": [
    {
      "document_id": 1,
      "document_title": "گزارش شرکت آریا",
      "document_snapshot_updated_at": "2026-08-13T12:00:00+03:30",
      "chunk_index": 0,
      "text": "در حال حاضر شرکت آریا ۱۲۰ نفر کارمند دارد."
    }
  ],
  "created_at": "2026-08-13T12:01:00+03:30"
}
```

## Documents

### `GET /api/documents/`

Lists Documents in newest-first order. No request body is required.

- Success: `200 OK` with a JSON array of Document objects.

```sh
curl http://127.0.0.1:8000/api/documents/
```

### `POST /api/documents/`

Uploads and indexes a DOCX document.

- Content type: `multipart/form-data`
- Fields: `title` (required string), `file` (required `.docx` file)
- Success: `201 Created` with the created Document.
- Errors: `400 Bad Request` for missing/invalid fields, unsupported extensions,
  or a corrupt DOCX; `503 Service Unavailable` when embedding configuration is
  missing; `502 Bad Gateway` when the embedding provider fails.

The SQLite Document remains saved if indexing fails; Chroma is derived state and
can be recovered with `python manage.py rebuild_document_index`.

```sh
curl -X POST http://127.0.0.1:8000/api/documents/ \
  -F 'title=گزارش شرکت آریا' \
  -F 'file=@sample_data/aria_company.docx'
```

### `GET /api/documents/{id}/`

Returns one Document.

- Success: `200 OK` with a Document object.
- Error: `404 Not Found` when the ID does not exist.

```sh
curl http://127.0.0.1:8000/api/documents/1/
```

### `PUT /api/documents/{id}/`

Fully updates a Document. Send multipart data when replacing the file. Because
this is a full update, required writable fields must be supplied.

- Content type: `multipart/form-data` or `application/json` when applicable
- Writable fields: `title`, `file`
- Success: `200 OK` with the updated Document.
- Errors: `400 Bad Request`, `404 Not Found`, `503 Service Unavailable` for
  embedding configuration, or `502 Bad Gateway` for an embedding-provider
  failure.

```sh
curl -X PUT http://127.0.0.1:8000/api/documents/1/ \
  -F 'title=گزارش به‌روز شرکت آریا' \
  -F 'file=@sample_data/aria_company.docx'
```

### `PATCH /api/documents/{id}/`

Partially updates a title and/or replaces a DOCX file. Title-only updates modify
Chroma metadata without re-embedding. File replacement embeds the complete new
chunk set before replacing the previous usable index.

- Content type: `application/json` for title-only changes or
  `multipart/form-data` for a file
- Success: `200 OK` with the updated Document.
- Errors: `400 Bad Request`, `404 Not Found`, `503 Service Unavailable`, or
  `502 Bad Gateway` as described above.

```sh
curl -X PATCH http://127.0.0.1:8000/api/documents/1/ \
  -H 'Content-Type: application/json' \
  -d '{"title":"گزارش جدید شرکت آریا"}'
```

### `DELETE /api/documents/{id}/`

Removes the Document and its indexed chunks.

- Success: `204 No Content` with an empty body.
- Errors: `404 Not Found`; `503 Service Unavailable` or `502 Bad Gateway` if
  accessing the configured Chroma collection fails through the handled
  embedding boundary.

```sh
curl -X DELETE http://127.0.0.1:8000/api/documents/1/
```

## Semantic retrieval

### `POST /api/search/`

Retrieves the nearest indexed chunks for a semantic query.

- Content type: `application/json`
- Fields: `query` (required non-empty string), `top_k` (optional JSON integer
  from 1 to 20, default 4)
- Success: `200 OK`
- Errors: `400 Bad Request` for invalid input; `503 Service Unavailable` when
  embeddings are not configured; `502 Bad Gateway` when the provider fails.

```sh
curl -X POST http://127.0.0.1:8000/api/search/ \
  -H 'Content-Type: application/json' \
  -d '{"query":"نیروی انسانی شرکت چند نفر است؟","top_k":4}'
```

```json
{
  "query": "نیروی انسانی شرکت چند نفر است؟",
  "results": [
    {
      "text": "در حال حاضر شرکت آریا ۱۲۰ نفر کارمند دارد.",
      "document_id": 1,
      "document_title": "گزارش شرکت آریا",
      "chunk_index": 0,
      "distance": 0.24
    }
  ]
}
```

`distance` is the vector-distance score returned by Chroma. It is not a
probability or confidence percentage. Lower values indicate nearer vectors
within the configured embedding space; values should not be compared across
different embedding models or collection configurations.

## Question answering and history

### `POST /api/questions/`

Retrieves context, asks the configured OpenRouter generation model through
LangChain, and saves a successful QuestionAnswer history row.

- Content type: `application/json`
- Field: `question` (required non-empty string)
- Success: `201 Created` with a QuestionAnswer object.
- Errors: `400 Bad Request` for invalid input; `503 Service Unavailable` when an
  OpenRouter key/embedding configuration is missing; `502 Bad Gateway` when the
  embedding or answer provider fails.

Provider/configuration failures do not create QuestionAnswer history rows. When
retrieval returns no chunks, generation is skipped and a deterministic
no-information answer is saved with an empty `context_snapshot`.

```sh
curl -X POST http://127.0.0.1:8000/api/questions/ \
  -H 'Content-Type: application/json' \
  -d '{"question":"نیروی انسانی شرکت چند نفر است؟"}'
```

### `GET /api/questions/`

Lists saved QuestionAnswer history in newest-first order.

- Success: `200 OK` with an array of QuestionAnswer objects.

```sh
curl http://127.0.0.1:8000/api/questions/
```

### `GET /api/questions/{id}/`

Returns one saved QuestionAnswer, including its immutable-at-answer-time
`context_snapshot`.

- Success: `200 OK` with a QuestionAnswer object.
- Error: `404 Not Found` when the ID does not exist.

```sh
curl http://127.0.0.1:8000/api/questions/1/
```
