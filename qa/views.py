from rest_framework import generics, status
from rest_framework.response import Response

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

    def post(self, request):
        input_serializer = QuestionInputSerializer(data=request.data)
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

        return Response(
            QuestionAnswerSerializer(question_answer).data,
            status=status.HTTP_201_CREATED,
        )


class QuestionAnswerDetailAPIView(generics.RetrieveAPIView):
    queryset = QuestionAnswer.objects.all()
    serializer_class = QuestionAnswerSerializer
