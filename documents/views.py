from rest_framework import parsers, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from documents.models import Document
from documents.serializers import DocumentSerializer, SearchSerializer
from documents.services.indexing import (
    delete_document_index,
    index_document,
    update_document_title,
)
from documents.services.retrieval import search_documents


class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    parser_classes = (parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser)

    def perform_create(self, serializer):
        document = serializer.save()
        index_document(document)

    def perform_update(self, serializer):
        file_changed = "file" in serializer.validated_data
        title_changed = "title" in serializer.validated_data
        document = serializer.save()
        if file_changed:
            index_document(document)
        elif title_changed:
            update_document_title(document)

    def perform_destroy(self, instance):
        delete_document_index(instance.pk)
        instance.delete()


class SearchAPIView(APIView):
    def post(self, request):
        serializer = SearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        query = serializer.validated_data["query"]
        top_k = serializer.validated_data["top_k"]
        results = search_documents(query, top_k=top_k)
        return Response(
            {"query": query, "results": results}, status=status.HTTP_200_OK
        )
