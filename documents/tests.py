import tempfile
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from docx import Document as DocxDocument
from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings
from rest_framework import status
from rest_framework.test import APIClient

from documents.models import Document
from documents.services import indexing
from documents.services.embeddings import EmbeddingUpstreamError
from documents.services.extraction import extract_docx_text


def make_docx_upload(name="example.docx", paragraphs=None):
    document = DocxDocument()
    for text in paragraphs or ["Example text"]:
        document.add_paragraph(text)

    output = BytesIO()
    document.save(output)
    return SimpleUploadedFile(
        name,
        output.getvalue(),
        content_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
    )


class ControlledEmbeddings(Embeddings):
    def __init__(self):
        self.error = None

    def embed_documents(self, texts):
        if self.error:
            raise self.error
        return [[1.0, float(index + 1)] for index, _text in enumerate(texts)]

    def embed_query(self, text):
        return [1.0, 0.0]


class TemporaryMediaTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.temporary_media = tempfile.TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.temporary_media.name)
        self.media_override.enable()

    def tearDown(self):
        self.media_override.disable()
        self.temporary_media.cleanup()
        super().tearDown()


class ExtractionAndModelTests(TemporaryMediaTestCase):
    def test_valid_docx_text_and_unicode_are_preserved(self):
        upload = make_docx_upload(
            paragraphs=["English paragraph.", "متن فارسی با نشانه‌گذاری!؟"]
        )

        content = extract_docx_text(upload)

        self.assertEqual(content, "English paragraph.\nمتن فارسی با نشانه‌گذاری!؟")

    def test_content_is_extracted_when_model_is_created(self):
        document = Document.objects.create(
            title="Stored document",
            file=make_docx_upload(paragraphs=["First", "دوم"]),
        )

        document.refresh_from_db()
        self.assertEqual(document.content, "First\nدوم")
        self.assertTrue(document.file.name.startswith("documents/"))

    def test_model_rejects_unsupported_extension(self):
        with self.assertRaisesMessage(ValidationError, "Only DOCX files"):
            Document.objects.create(
                title="PDF",
                file=SimpleUploadedFile("example.pdf", b"not a PDF"),
            )

    def test_model_rejects_malformed_docx(self):
        with self.assertRaisesMessage(ValidationError, "not a valid DOCX"):
            Document.objects.create(
                title="Broken",
                file=SimpleUploadedFile("broken.docx", b"not a zip package"),
            )


class DocumentApiTests(TemporaryMediaTestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.list_url = reverse("document-list")
        self.index_document = patch("documents.views.index_document").start()
        self.update_document_title = patch(
            "documents.views.update_document_title"
        ).start()
        self.delete_document_index = patch(
            "documents.views.delete_document_index"
        ).start()
        self.addCleanup(patch.stopall)

    def create_document(self, title="API document", text="Original content"):
        response = self.client.post(
            self.list_url,
            {"title": title, "file": make_docx_upload(paragraphs=[text])},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return response

    def test_create_document_extracts_and_returns_content(self):
        response = self.create_document(text="API متن")

        document = Document.objects.get(pk=response.data["id"])
        self.assertEqual(document.content, "API متن")
        self.assertEqual(response.data["content"], "API متن")
        self.index_document.assert_called_once_with(document)

    def test_create_embedding_failure_is_clear_after_document_save(self):
        self.index_document.side_effect = EmbeddingUpstreamError("provider detail")

        response = self.client.post(
            self.list_url,
            {
                "title": "Saved but not indexed",
                "file": make_docx_upload(paragraphs=["Content"]),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(Document.objects.count(), 1)
        self.assertEqual(
            response.data,
            {"detail": "The embedding provider is temporarily unavailable."},
        )

    def test_list_and_retrieve_documents(self):
        created = self.create_document(title="Listed", text="List content")

        list_response = self.client.get(self.list_url)
        detail_response = self.client.get(
            reverse("document-detail", args=[created.data["id"]])
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(list_response.data[0]["title"], "Listed")
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["content"], "List content")

    def test_title_update_preserves_file_and_content_without_reextraction(self):
        created = self.create_document(text="Unchanged content")
        document = Document.objects.get(pk=created.data["id"])
        original_file_name = document.file.name
        detail_url = reverse("document-detail", args=[document.pk])
        self.index_document.reset_mock()

        with patch("documents.models.validate_and_extract_docx") as extractor:
            response = self.client.patch(
                detail_url, {"title": "Renamed"}, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        extractor.assert_not_called()
        document.refresh_from_db()
        self.assertEqual(document.title, "Renamed")
        self.assertEqual(document.file.name, original_file_name)
        self.assertEqual(document.content, "Unchanged content")
        self.index_document.assert_not_called()
        self.update_document_title.assert_called_once_with(document)

    def test_replacing_file_updates_extracted_content(self):
        created = self.create_document(text="Old content")
        detail_url = reverse("document-detail", args=[created.data["id"]])
        self.index_document.reset_mock()

        response = self.client.patch(
            detail_url,
            {"file": make_docx_upload("replacement.docx", ["New", "محتوا"])},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        document = Document.objects.get(pk=created.data["id"])
        self.assertEqual(document.content, "New\nمحتوا")
        self.assertIn("replacement", document.file.name)
        self.index_document.assert_called_once_with(document)

    def test_file_update_embedding_failure_is_clear_after_document_save(self):
        created = self.create_document(text="Old content")
        embeddings = ControlledEmbeddings()
        temporary_chroma = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_chroma.cleanup)
        vector_store = Chroma(
            collection_name=f"test_replacement_{uuid4().hex}",
            embedding_function=embeddings,
            persist_directory=temporary_chroma.name,
        )
        vector_store_patch = patch(
            "documents.services.indexing.get_vector_store", return_value=vector_store
        )
        embeddings_patch = patch(
            "documents.services.indexing.get_embeddings", return_value=embeddings
        )
        vector_store_patch.start()
        embeddings_patch.start()
        self.addCleanup(vector_store_patch.stop)
        self.addCleanup(embeddings_patch.stop)

        document = Document.objects.get(pk=created.data["id"])
        indexing.index_document(document)
        old_records = vector_store.get(where={"document_id": document.pk})

        self.index_document.reset_mock()
        self.index_document.side_effect = indexing.index_document
        embeddings.error = EmbeddingUpstreamError("provider detail")

        response = self.client.patch(
            reverse("document-detail", args=[created.data["id"]]),
            {"file": make_docx_upload("replacement.docx", ["New content"])},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        document.refresh_from_db()
        self.assertEqual(document.content, "New content")
        self.assertEqual(
            vector_store.get(where={"document_id": document.pk}), old_records
        )

    def test_same_named_replacement_still_updates_content(self):
        created = self.create_document(text="Old same-name content")
        document = Document.objects.get(pk=created.data["id"])
        original_basename = document.file.name.rsplit("/", 1)[-1]

        response = self.client.patch(
            reverse("document-detail", args=[document.pk]),
            {"file": make_docx_upload(original_basename, ["New same-name content"])},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        document.refresh_from_db()
        self.assertEqual(document.content, "New same-name content")

    def test_delete_document(self):
        created = self.create_document()
        self.delete_document_index.reset_mock()

        response = self.client.delete(
            reverse("document-detail", args=[created.data["id"]])
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Document.objects.filter(pk=created.data["id"]).exists())
        self.delete_document_index.assert_called_once_with(created.data["id"])

    def test_non_docx_upload_returns_clear_400(self):
        response = self.client.post(
            self.list_url,
            {
                "title": "Unsupported",
                "file": SimpleUploadedFile(
                    "example.pdf", b"%PDF fake", content_type="application/pdf"
                ),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("file", response.data)
        self.assertIn("Only DOCX", str(response.data["file"]))

    def test_malformed_docx_returns_clear_400(self):
        response = self.client.post(
            self.list_url,
            {
                "title": "Malformed",
                "file": SimpleUploadedFile("corrupt.docx", b"not a DOCX"),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("file", response.data)
        self.assertIn("not a valid DOCX", str(response.data["file"]))
        self.assertEqual(Document.objects.count(), 0)


class DocumentAdminTests(TemporaryMediaTestCase):
    def setUp(self):
        super().setUp()
        user_model = get_user_model()
        self.admin_user = user_model.objects.create_superuser(
            username="admin", email="admin@example.com", password="password"
        )
        self.client.force_login(self.admin_user)
        self.index_document = patch("documents.admin.index_document").start()
        self.update_document_title = patch(
            "documents.admin.update_document_title"
        ).start()
        self.delete_document_index = patch(
            "documents.admin.delete_document_index"
        ).start()
        self.addCleanup(patch.stopall)

    def test_admin_upload_extracts_content(self):
        response = self.client.post(
            reverse("admin:documents_document_add"),
            {
                "title": "Admin upload",
                "file": make_docx_upload(paragraphs=["Admin content", "فارسی"]),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        document = Document.objects.get()
        self.assertEqual(document.content, "Admin content\nفارسی")
        self.index_document.assert_called_once_with(document)

    def test_admin_title_update_only_updates_index_metadata(self):
        document = Document.objects.create(
            title="Old admin title",
            file=make_docx_upload(paragraphs=["Stable content"]),
        )

        response = self.client.post(
            reverse("admin:documents_document_change", args=[document.pk]),
            {"title": "New admin title"},
        )

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        document.refresh_from_db()
        self.assertEqual(document.title, "New admin title")
        self.index_document.assert_not_called()
        self.update_document_title.assert_called_once_with(document)

    def test_admin_file_update_reindexes_extracted_content(self):
        document = Document.objects.create(
            title="Admin replacement",
            file=make_docx_upload(paragraphs=["Old admin content"]),
        )

        response = self.client.post(
            reverse("admin:documents_document_change", args=[document.pk]),
            {
                "title": document.title,
                "file": make_docx_upload("admin-new.docx", ["New admin content"]),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        document.refresh_from_db()
        self.assertEqual(document.content, "New admin content")
        self.index_document.assert_called_once_with(document)
        self.update_document_title.assert_not_called()

    def test_admin_delete_removes_document_index(self):
        document = Document.objects.create(
            title="Delete through admin",
            file=make_docx_upload(paragraphs=["Delete me"]),
        )
        document_id = document.pk

        response = self.client.post(
            reverse("admin:documents_document_delete", args=[document_id]),
            {"post": "yes"},
        )

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertFalse(Document.objects.filter(pk=document_id).exists())
        self.delete_document_index.assert_called_once_with(document_id)

    def test_admin_malformed_upload_is_a_form_error(self):
        response = self.client.post(
            reverse("admin:documents_document_add"),
            {
                "title": "Bad admin upload",
                "file": SimpleUploadedFile("bad.docx", b"broken"),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "not a valid DOCX")
        self.assertEqual(Document.objects.count(), 0)
