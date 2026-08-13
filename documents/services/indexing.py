from functools import lru_cache
from pathlib import Path

from django.conf import settings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

from documents.services.embeddings import OpenRouterEmbeddings


@lru_cache(maxsize=4)
def _build_embeddings(
    api_key: str,
    model_name: str,
    timeout_ms: int,
    retries: int,
) -> OpenRouterEmbeddings:
    return OpenRouterEmbeddings(
        api_key=api_key,
        model=model_name,
        timeout_ms=timeout_ms,
        retries=retries,
    )


def get_embeddings() -> OpenRouterEmbeddings:
    """Return a process-reused OpenRouter embedding client."""
    return _build_embeddings(
        settings.OPENROUTER_API_KEY,
        settings.OPENROUTER_EMBEDDING_MODEL,
        settings.OPENROUTER_EMBEDDING_TIMEOUT_MS,
        settings.OPENROUTER_EMBEDDING_RETRIES,
    )


@lru_cache(maxsize=8)
def _build_vector_store(
    persist_directory: str,
    collection_name: str,
    api_key: str,
    model_name: str,
    timeout_ms: int,
    retries: int,
) -> Chroma:
    Path(persist_directory).mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=collection_name,
        embedding_function=_build_embeddings(
            api_key, model_name, timeout_ms, retries
        ),
        persist_directory=persist_directory,
    )


def get_vector_store() -> Chroma:
    """Open the configured persistent collection, reusing it in this process."""
    return _build_vector_store(
        str(settings.CHROMA_PERSIST_DIRECTORY),
        settings.CHROMA_COLLECTION_NAME,
        settings.OPENROUTER_API_KEY,
        settings.OPENROUTER_EMBEDDING_MODEL,
        settings.OPENROUTER_EMBEDDING_TIMEOUT_MS,
        settings.OPENROUTER_EMBEDDING_RETRIES,
    )


def split_document_content(content: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.DOCUMENT_CHUNK_SIZE,
        chunk_overlap=settings.DOCUMENT_CHUNK_OVERLAP,
        length_function=len,
        is_separator_regex=False,
    )
    return splitter.split_text(content)


def chunk_id(document_id: int, chunk_index: int) -> str:
    return f"document-{document_id}-chunk-{chunk_index}"


def _ids_for_document(document_id: int) -> list[str]:
    records = get_vector_store().get(where={"document_id": document_id})
    return list(records.get("ids", []))


def delete_document_index(document_id: int) -> None:
    """Remove every indexed chunk for a database document."""
    ids = _ids_for_document(document_id)
    if ids:
        get_vector_store().delete(ids=ids)


def index_document(document) -> int:
    """Replace a document's derived Chroma records with its current content."""
    delete_document_index(document.pk)
    chunks = split_document_content(document.content)
    if not chunks:
        return 0

    metadatas = [
        {
            "document_id": document.pk,
            "document_title": document.title,
            "chunk_index": index,
        }
        for index, _chunk in enumerate(chunks)
    ]
    ids = [chunk_id(document.pk, index) for index, _chunk in enumerate(chunks)]
    get_vector_store().add_texts(texts=chunks, metadatas=metadatas, ids=ids)
    return len(chunks)


def update_document_title(document) -> int:
    """Update source metadata without re-chunking or re-embedding text."""
    vector_store = get_vector_store()
    records = vector_store.get(
        where={"document_id": document.pk}, include=["metadatas"]
    )
    ids = list(records.get("ids", []))
    if not ids:
        return 0

    metadatas = [
        {**metadata, "document_title": document.title}
        for metadata in records.get("metadatas", [])
    ]
    # LangChain's document update API re-embeds content. Chroma's metadata-only
    # update preserves the existing vectors, which is required for title changes.
    vector_store._collection.update(ids=ids, metadatas=metadatas)
    return len(ids)
