from rest_framework import generics, status
from rest_framework.response import Response

from documents.services.embeddings import (
    EmbeddingConfigurationError,
    EmbeddingUpstreamError,
)
from qa.models import QuestionAnswer
from qa.serializers import QuestionAnswerSerializer, QuestionInputSerializer
from qa.services.generation import (
    GenerationConfigurationError,
    UpstreamGenerationError,
)
from qa.services.qa import answer_question


class QuestionAnswerListCreateAPIView(generics.ListAPIView):
    queryset = QuestionAnswer.objects.all()
    serializer_class = QuestionAnswerSerializer

    def get_serializer_class(self):
        if self.request.method == "POST":
            return QuestionInputSerializer
        return QuestionAnswerSerializer

    def post(self, request):
        input_serializer = self.get_serializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        try:
            question_answer = answer_question(
                input_serializer.validated_data["question"]
            )
        except GenerationConfigurationError as exc:
            return Response(
                {"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except UpstreamGenerationError:
            return Response(
                {"detail": "The answer provider is temporarily unavailable."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except EmbeddingConfigurationError:
            return Response(
                {"detail": "Document embeddings are not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except EmbeddingUpstreamError:
            return Response(
                {"detail": "The embedding provider is temporarily unavailable."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            QuestionAnswerSerializer(question_answer).data,
            status=status.HTTP_201_CREATED,
        )


class QuestionAnswerDetailAPIView(generics.RetrieveAPIView):
    queryset = QuestionAnswer.objects.all()
    serializer_class = QuestionAnswerSerializer
