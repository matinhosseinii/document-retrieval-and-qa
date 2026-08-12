from documents.services.indexing import get_vector_store


def search_documents(query: str, top_k: int = 4) -> list[dict]:
    """Return semantically nearest indexed chunks and their source metadata."""
    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("Query must not be empty.")

    documents_with_distances = get_vector_store().similarity_search_with_score(
        normalized_query,
        k=top_k,
    )

    return [
        {
            "text": document.page_content,
            "document_id": document.metadata["document_id"],
            "document_title": document.metadata["document_title"],
            "chunk_index": document.metadata["chunk_index"],
            "distance": float(distance),
        }
        for document, distance in documents_with_distances
    ]
