from django.db import models


class QuestionAnswer(models.Model):
    question = models.TextField()
    answer = models.TextField()
    context_snapshot = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.question
