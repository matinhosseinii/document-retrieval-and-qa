from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from documents.models import Document
from documents.services.extraction import validate_and_extract_docx


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ("id", "title", "file", "content", "created_at", "updated_at")
        read_only_fields = ("id", "content", "created_at", "updated_at")

    def validate_file(self, file):
        try:
            validate_and_extract_docx(file)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        return file
