from django import forms

from documents.models import Document
from documents.services.extraction import validate_and_extract_docx


class DocumentAdminForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = "__all__"

    def clean_file(self):
        file = self.cleaned_data["file"]
        if "file" in self.changed_data:
            validate_and_extract_docx(file)
        return file
