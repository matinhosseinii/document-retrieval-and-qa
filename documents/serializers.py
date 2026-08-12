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


class StrictStringField(serializers.CharField):
    default_error_messages = {"invalid": "Must be a string."}

    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail("invalid")
        return super().to_internal_value(data)


class StrictIntegerField(serializers.IntegerField):
    default_error_messages = {"invalid": "A valid integer is required."}

    def to_internal_value(self, data):
        if isinstance(data, bool) or not isinstance(data, int):
            self.fail("invalid")
        return super().to_internal_value(data)


class SearchSerializer(serializers.Serializer):
    query = StrictStringField(allow_blank=False, trim_whitespace=True)
    top_k = StrictIntegerField(required=False, default=4, min_value=1, max_value=20)
