from django.contrib import admin

from documents.forms import DocumentAdminForm
from documents.models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    form = DocumentAdminForm
    list_display = ("id", "title", "created_at", "updated_at")
    search_fields = ("title", "content")
    readonly_fields = ("content", "created_at", "updated_at")
