from django.urls import path

from qa.views import QuestionAnswerDetailAPIView, QuestionAnswerListCreateAPIView


urlpatterns = [
    path(
        "questions/",
        QuestionAnswerListCreateAPIView.as_view(),
        name="question-answer-list",
    ),
    path(
        "questions/<int:pk>/",
        QuestionAnswerDetailAPIView.as_view(),
        name="question-answer-detail",
    ),
]
