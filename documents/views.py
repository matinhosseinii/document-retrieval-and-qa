from rest_framework import parsers, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from documents.api_exceptions import (
    EmbeddingConfigurationAPIError,
    EmbeddingUpstreamAPIError,
)
from documents.models import Document
from documents.serializers import DocumentSerializer, SearchSerializer
from documents.services.indexing import (
    delete_document_index,
    index_document,
    update_document_title,
)
from documents.services.retrieval import search_documents
from documents.services.embeddings import (
    EmbeddingConfigurationError,
    EmbeddingUpstreamError,
)


def _raise_embedding_api_error(exc):
    if isinstance(exc, EmbeddingConfigurationError):
        raise EmbeddingConfigurationAPIError() from exc
    raise EmbeddingUpstreamAPIError() from exc


class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    parser_classes = (parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser)

    def perform_create(self, serializer):
        document = serializer.save()
        try:
            index_document(document)
        except (EmbeddingConfigurationError, EmbeddingUpstreamError) as exc:
            _raise_embedding_api_error(exc)

    def perform_update(self, serializer):
        file_changed = "file" in serializer.validated_data
        title_changed = "title" in serializer.validated_data
        document = serializer.save()
        try:
            if file_changed:
                index_document(document)
            elif title_changed:
                update_document_title(document)
        except (EmbeddingConfigurationError, EmbeddingUpstreamError) as exc:
            _raise_embedding_api_error(exc)

    def perform_destroy(self, instance):
        try:
            delete_document_index(instance.pk)
        except (EmbeddingConfigurationError, EmbeddingUpstreamError) as exc:
            _raise_embedding_api_error(exc)
        instance.delete()


class SearchAPIView(APIView):
    def post(self, request):
        serializer = SearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        query = serializer.validated_data["query"]
        top_k = serializer.validated_data["top_k"]
        try:
            results = search_documents(query, top_k=top_k)
        except (EmbeddingConfigurationError, EmbeddingUpstreamError) as exc:
            _raise_embedding_api_error(exc)
        return Response(
            {"query": query, "results": results}, status=status.HTTP_200_OK
        )
