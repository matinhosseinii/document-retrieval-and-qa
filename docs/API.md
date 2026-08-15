# API Reference

The API is available at `http://127.0.0.1:8000/api/`. It requires no
authentication. Requests and responses use JSON unless an endpoint specifies
`multipart/form-data`.

List endpoints use page-number pagination with five items per page. Pass an
optional positive integer as `?page=2`. Paginated responses have this shape:

```json
{
  "count": 7,
  "next": "http://127.0.0.1:8000/api/documents/?page=2",
  "previous": null,
  "results": []
}
```

## `GET /api/documents/`

Lists documents in newest-first order.

### Request

Query parameters:

- `page` (optional integer): Page number.

### Response

Status: `200 OK`

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "title": "Company profile",
      "file": "http://127.0.0.1:8000/media/documents/company.docx",
      "content": "The company office is in Tehran.",
      "created_at": "2026-08-15T10:00:00+03:30",
      "updated_at": "2026-08-15T10:00:00+03:30"
    }
  ]
}
```

### Errors

- `404 Not Found` if `page` is invalid or outside the available range.

## `POST /api/documents/`

Uploads a DOCX document, extracts its paragraph text, and indexes it for search.

### Request

Content type: `multipart/form-data`

- `title` (required string, maximum 255 characters): Document title.
- `file` (required file): A valid file with a `.docx` extension.

```sh
curl -X POST http://127.0.0.1:8000/api/documents/ \
  -F 'title=Company profile' \
  -F 'file=@/path/to/company.docx'
```

### Response

Status: `201 Created`

```json
{
  "id": 1,
  "title": "Company profile",
  "file": "http://127.0.0.1:8000/media/documents/company.docx",
  "content": "The company office is in Tehran.",
  "created_at": "2026-08-15T10:00:00+03:30",
  "updated_at": "2026-08-15T10:00:00+03:30"
}
```

`id`, `content`, `created_at`, and `updated_at` are read-only. The file URL,
extracted content, and timestamps depend on the uploaded document and server
configuration.

### Errors

- `400 Bad Request` for missing fields, a non-DOCX file, or an invalid DOCX file.
- `503 Service Unavailable` if document embeddings are not configured.
- `502 Bad Gateway` if the embedding provider is unavailable or returns an
  invalid response.

The document is stored in SQLite before indexing. An indexing error can
therefore return `502` or `503` after the document has been saved.

## `GET /api/documents/{id}/`

Returns one document and its extracted content.

### Request

Path parameters:

- `id` (required integer): Document ID.

### Response

Status: `200 OK`

```json
{
  "id": 1,
  "title": "Company profile",
  "file": "http://127.0.0.1:8000/media/documents/company.docx",
  "content": "The company office is in Tehran.",
  "created_at": "2026-08-15T10:00:00+03:30",
  "updated_at": "2026-08-15T10:00:00+03:30"
}
```

### Errors

- `404 Not Found` if the document does not exist.

## `PUT /api/documents/{id}/`

Replaces a document's writable fields and reindexes its extracted content.

### Request

Content type: `multipart/form-data`

Path parameters:

- `id` (required integer): Document ID.

Form fields:

- `title` (required string, maximum 255 characters): Document title.
- `file` (required file): A valid file with a `.docx` extension.

```sh
curl -X PUT http://127.0.0.1:8000/api/documents/1/ \
  -F 'title=Updated company profile' \
  -F 'file=@sample_data/aria_company.docx'
```

### Response

Status: `200 OK`

```json
{
  "id": 1,
  "title": "Updated company profile",
  "file": "http://127.0.0.1:8000/media/documents/aria_company.docx",
  "content": "معرفی شرکت آریا\nشرکت آریا در سال ۱۳۹۵ تأسیس شد.\nدفتر مرکزی شرکت در تهران قرار دارد.\nدر حال حاضر شرکت آریا ۱۲۰ نفر کارمند دارد.\nمحصول اصلی شرکت یک سامانه مدیریت منابع انسانی ابری است.\nمدیرعامل شرکت نسترن رضایی است.",
  "created_at": "2026-08-15T10:00:00+03:30",
  "updated_at": "2026-08-15T10:05:00+03:30"
}
```

### Errors

- `400 Bad Request` for missing or invalid fields.
- `404 Not Found` if the document does not exist.
- `503 Service Unavailable` if document embeddings are not configured.
- `502 Bad Gateway` if the embedding provider is unavailable or returns an
  invalid response.

The database record is updated before indexing. An indexing error can therefore
return `502` or `503` after the new values have been saved.

## `PATCH /api/documents/{id}/`

Updates the document title, file, or both. Replacing the file reindexes its
content; changing only the title updates the indexed title metadata.

### Request

Path parameters:

- `id` (required integer): Document ID.

For a title-only update, use `application/json`:

```json
{
  "title": "Updated company profile"
}
```

For a file replacement, use `multipart/form-data`:

```sh
curl -X PATCH http://127.0.0.1:8000/api/documents/1/ \
  -F 'file=@sample_data/aria_company.docx'
```

Both `title` (string, maximum 255 characters) and `file` (valid `.docx` file)
are optional.

### Response

Status: `200 OK`

```json
{
  "id": 1,
  "title": "Updated company profile",
  "file": "http://127.0.0.1:8000/media/documents/aria_company.docx",
  "content": "معرفی شرکت آریا\nشرکت آریا در سال ۱۳۹۵ تأسیس شد.\nدفتر مرکزی شرکت در تهران قرار دارد.\nدر حال حاضر شرکت آریا ۱۲۰ نفر کارمند دارد.\nمحصول اصلی شرکت یک سامانه مدیریت منابع انسانی ابری است.\nمدیرعامل شرکت نسترن رضایی است.",
  "created_at": "2026-08-15T10:00:00+03:30",
  "updated_at": "2026-08-15T10:05:00+03:30"
}
```

### Errors

- `400 Bad Request` for invalid fields.
- `404 Not Found` if the document does not exist.
- `503 Service Unavailable` if document embeddings are not configured.
- `502 Bad Gateway` if the embedding provider is unavailable or returns an
  invalid response.

The database record is updated before the index. An indexing error can therefore
return `502` or `503` after the new values have been saved.

## `DELETE /api/documents/{id}/`

Deletes a document and its indexed chunks.

### Request

Path parameters:

- `id` (required integer): Document ID.

### Response

Status: `204 No Content` with an empty body.

### Errors

- `404 Not Found` if the document does not exist.
- `503 Service Unavailable` if document embeddings are not configured.

If index deletion fails, the database record is not deleted.

## `POST /api/search/`

Returns the nearest indexed document chunks for a natural-language query.

### Request

```json
{
  "query": "Where is the company office?",
  "top_k": 4
}
```

- `query` (required string): A non-empty search query.
- `top_k` (optional integer): Number of results, from 1 to 20. Defaults to 4.

### Response

Status: `200 OK`

```json
{
  "query": "Where is the company office?",
  "results": [
    {
      "text": "The company office is in Tehran.",
      "document_id": 1,
      "document_title": "Company profile",
      "chunk_index": 0,
      "distance": 0.24
    }
  ]
}
```

Results are ordered by vector distance. Lower distances indicate nearer matches;
the value is not a probability. The API may return fewer than `top_k` results.

### Errors

- `400 Bad Request` if `query` or `top_k` is invalid.
- `503 Service Unavailable` if document embeddings are not configured.
- `502 Bad Gateway` if the embedding provider is unavailable or returns an
  invalid response.

## `GET /api/questions/`

Lists saved question-and-answer records in newest-first order.

### Request

Query parameters:

- `page` (optional integer): Page number.

### Response

Status: `200 OK`

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "question": "Where is the company office?",
      "answer": "The company office is in Tehran.",
      "context_snapshot": [
        {
          "document_id": 1,
          "document_title": "Company profile",
          "document_snapshot_updated_at": "2026-08-15T10:00:00+03:30",
          "chunk_index": 0,
          "text": "The company office is in Tehran."
        }
      ],
      "created_at": "2026-08-15T10:01:00+03:30"
    }
  ]
}
```

### Errors

- `404 Not Found` if `page` is invalid or outside the available range.

## `POST /api/questions/`

Retrieves document context, generates an answer, and saves the result in question
history.

### Request

```json
{
  "question": "Where is the company office?"
}
```

- `question` (required string): A non-empty question.

### Response

Status: `201 Created`

```json
{
  "id": 1,
  "question": "Where is the company office?",
  "answer": "The company office is in Tehran.",
  "context_snapshot": [
    {
      "document_id": 1,
      "document_title": "Company profile",
      "document_snapshot_updated_at": "2026-08-15T10:00:00+03:30",
      "chunk_index": 0,
      "text": "The company office is in Tehran."
    }
  ],
  "created_at": "2026-08-15T10:01:00+03:30"
}
```

The answer is based only on the retrieved context. If no chunks are retrieved,
the API saves the answer `No relevant information was found in the available
documents.` with an empty `context_snapshot` and does not call the generation
model.

### Errors

- `400 Bad Request` if `question` is missing, empty, or not a string.
- `503 Service Unavailable` if the OpenRouter API key or embeddings are not
  configured.
- `502 Bad Gateway` if the embedding or answer provider is unavailable.

Provider and configuration failures do not create a question-history record.

## `GET /api/questions/{id}/`

Returns one saved question-and-answer record with its captured document context.

### Request

Path parameters:

- `id` (required integer): Question-and-answer record ID.

### Response

Status: `200 OK`

```json
{
  "id": 1,
  "question": "Where is the company office?",
  "answer": "The company office is in Tehran.",
  "context_snapshot": [
    {
      "document_id": 1,
      "document_title": "Company profile",
      "document_snapshot_updated_at": "2026-08-15T10:00:00+03:30",
      "chunk_index": 0,
      "text": "The company office is in Tehran."
    }
  ],
  "created_at": "2026-08-15T10:01:00+03:30"
}
```

### Errors

- `404 Not Found` if the record does not exist.
