from documents.models import Document
from documents.services.retrieval import search_documents
from qa.models import QuestionAnswer
from qa.services.generation import generate_answer


NO_CONTEXT_ANSWER = "No relevant information was found in the available documents."


def _create_context_snapshot(retrieval_results: list[dict]) -> list[dict]:
    document_ids = {result["document_id"] for result in retrieval_results}
    updated_at_by_id = dict(
        Document.objects.filter(pk__in=document_ids).values_list("pk", "updated_at")
    )

    return [
        {
            "document_id": result["document_id"],
            "document_title": result["document_title"],
            "document_snapshot_updated_at": (
                updated_at_by_id[result["document_id"]].isoformat()
                if result["document_id"] in updated_at_by_id
                else None
            ),
            "chunk_index": result["chunk_index"],
            "text": result["text"],
        }
        for result in retrieval_results
    ]


def answer_question(question: str) -> QuestionAnswer:
    retrieval_results = search_documents(question, top_k=4)
    context_snapshot = _create_context_snapshot(retrieval_results)
    answer = (
        generate_answer(question, context_snapshot)
        if context_snapshot
        else NO_CONTEXT_ANSWER
    )
    return QuestionAnswer.objects.create(
        question=question,
        answer=answer,
        context_snapshot=context_snapshot,
    )
