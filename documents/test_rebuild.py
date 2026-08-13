from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from documents.models import Document
from documents.services.indexing import chunk_id, split_document_content


class FakeRebuildVectorStore:
    def __init__(self, ids=None):
        self.ids = list(ids or [])
        self.deleted = []

    def get(self):
        return {"ids": list(self.ids)}

    def delete(self, ids):
        self.deleted.extend(ids)
        self.ids = [record_id for record_id in self.ids if record_id not in ids]


@override_settings(DOCUMENT_CHUNK_SIZE=20, DOCUMENT_CHUNK_OVERLAP=5)
class RebuildDocumentIndexCommandTests(TestCase):
    def setUp(self):
        self.first = Document.objects.create(
            title="First", file="", content="First content " * 4
        )
        self.second = Document.objects.create(
            title="Second", file="", content="متن فارسی " * 4
        )

    @patch("documents.management.commands.rebuild_document_index.index_document")
    @patch("documents.management.commands.rebuild_document_index.get_vector_store")
    def test_populated_target_requires_force(self, get_store, index_document):
        get_store.return_value = FakeRebuildVectorStore(["existing-vector"])

        with self.assertRaisesMessage(CommandError, "not empty"):
            call_command("rebuild_document_index", stdout=StringIO())

        index_document.assert_not_called()

    @patch("documents.management.commands.rebuild_document_index.index_document")
    @patch("documents.management.commands.rebuild_document_index.get_vector_store")
    def test_force_clears_only_target_and_verifies_chunk_coverage(
        self, get_store, index_document
    ):
        store = FakeRebuildVectorStore(["old-target-vector"])
        get_store.return_value = store

        def index(document):
            chunks = split_document_content(document.content)
            store.ids.extend(
                chunk_id(document.pk, index) for index, _chunk in enumerate(chunks)
            )
            return len(chunks)

        index_document.side_effect = index
        output = StringIO()

        call_command("rebuild_document_index", "--force", stdout=output)

        self.assertEqual(store.deleted, ["old-target-vector"])
        self.assertEqual(index_document.call_count, 2)
        self.assertIn("Failures: 0", output.getvalue())
        self.assertIn("rebuilt successfully", output.getvalue())
