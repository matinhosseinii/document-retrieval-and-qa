from functools import lru_cache
from pathlib import Path

from django.conf import settings
from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter


class E5Embeddings(Embeddings):
    """Apply the asymmetric prefixes required by multilingual E5 models."""

    def __init__(self, embeddings: Embeddings):
        self.embeddings = embeddings

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embeddings.embed_documents(
            [f"passage: {text}" for text in texts]
        )

    def embed_query(self, text: str) -> list[float]:
        return self.embeddings.embed_query(f"query: {text}")


@lru_cache(maxsize=4)
def _build_embeddings(model_name: str, device: str) -> E5Embeddings:
    embeddings = HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={"device": device},
        encode_kwargs={"normalize_embeddings": True},
    )
    return E5Embeddings(embeddings)


def get_embeddings() -> E5Embeddings:
    """Return a process-reused local embedding model."""
    return _build_embeddings(settings.EMBEDDING_MODEL_NAME, settings.EMBEDDING_DEVICE)


@lru_cache(maxsize=8)
def _build_vector_store(
    persist_directory: str,
    collection_name: str,
    model_name: str,
    device: str,
) -> Chroma:
    Path(persist_directory).mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=collection_name,
        embedding_function=_build_embeddings(model_name, device),
        persist_directory=persist_directory,
    )


def get_vector_store() -> Chroma:
    """Open the configured persistent collection, reusing it in this process."""
    return _build_vector_store(
        str(settings.CHROMA_PERSIST_DIRECTORY),
        settings.CHROMA_COLLECTION_NAME,
        settings.EMBEDDING_MODEL_NAME,
        settings.EMBEDDING_DEVICE,
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
