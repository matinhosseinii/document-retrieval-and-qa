from rest_framework import serializers

from qa.models import QuestionAnswer


class StrictQuestionField(serializers.CharField):
    default_error_messages = {"invalid": "Must be a string."}

    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail("invalid")
        return super().to_internal_value(data)


class QuestionInputSerializer(serializers.Serializer):
    question = StrictQuestionField(allow_blank=False, trim_whitespace=True)


class QuestionAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionAnswer
        fields = ("id", "question", "answer", "context_snapshot", "created_at")
        read_only_fields = fields
