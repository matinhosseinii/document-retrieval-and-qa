from django.contrib import admin

from qa.models import QuestionAnswer


@admin.register(QuestionAnswer)
class QuestionAnswerAdmin(admin.ModelAdmin):
    list_display = ("id", "question", "answer", "created_at")
    search_fields = ("question", "answer")
    readonly_fields = ("question", "answer", "context_snapshot", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
