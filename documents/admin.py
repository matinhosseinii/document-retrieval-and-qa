from django.contrib import admin

from documents.forms import DocumentAdminForm
from documents.models import Document
from documents.services.indexing import (
    delete_document_index,
    index_document,
    update_document_title,
)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    form = DocumentAdminForm
    list_display = ("id", "title", "created_at", "updated_at")
    search_fields = ("title", "content")
    readonly_fields = ("content", "created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change or "file" in form.changed_data:
            index_document(obj)
        elif "title" in form.changed_data:
            update_document_title(obj)

    def delete_model(self, request, obj):
        delete_document_index(obj.pk)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for document_id in queryset.values_list("pk", flat=True):
            delete_document_index(document_id)
        super().delete_queryset(request, queryset)
