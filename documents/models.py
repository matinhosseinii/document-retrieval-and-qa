from django.db import models

from documents.services.extraction import (
    clear_extracted_text_cache,
    has_extracted_text_cache,
    validate_and_extract_docx,
    validate_docx_extension,
)


class Document(models.Model):
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to="documents/", validators=[validate_docx_extension])
    content = models.TextField(blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_file_name = self.file.name

    def __str__(self):
        return self.title

    def _uploaded_file(self):
        return getattr(self.file, "_file", None)

    def _file_requires_extraction(self):
        uploaded_file = self._uploaded_file()
        return (
            self._state.adding
            or self.file.name != self._original_file_name
            or has_extracted_text_cache(uploaded_file)
        )

    def save(self, *args, **kwargs):
        should_extract = bool(self.file) and self._file_requires_extraction()
        uploaded_file = self._uploaded_file()

        if should_extract:
            self.content = validate_and_extract_docx(self.file)
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {"file", "content"}

        super().save(*args, **kwargs)
        self._original_file_name = self.file.name

        clear_extracted_text_cache(self.file)
        if uploaded_file is not None:
            clear_extracted_text_cache(uploaded_file)
