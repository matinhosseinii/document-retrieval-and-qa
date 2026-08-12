import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from langchain_chroma import Chroma
from langchain_core.documents import Document as LangChainDocument
from langchain_core.embeddings import Embeddings
from rest_framework import status
from rest_framework.test import APIClient

from documents.services import indexing, retrieval


class FakeCollection:
    def __init__(self, store):
        self.store = store

    def update(self, ids, metadatas):
        for record_id, metadata in zip(ids, metadatas, strict=True):
            self.store.records[record_id]["metadata"] = metadata


class FakeVectorStore:
    def __init__(self):
        self.records = {}
        self.add_calls = 0
        self.search_results = []
        self.last_search = None
        self._collection = FakeCollection(self)

    def add_texts(self, texts, metadatas, ids):
        self.add_calls += 1
        for record_id, text, metadata in zip(ids, texts, metadatas, strict=True):
            self.records[record_id] = {"text": text, "metadata": metadata}
        return ids

    def get(self, where, include=None):
        matched = [
            (record_id, record)
            for record_id, record in self.records.items()
            if all(record["metadata"].get(key) == value for key, value in where.items())
        ]
        return {
            "ids": [record_id for record_id, _record in matched],
            "documents": [record["text"] for _record_id, record in matched],
            "metadatas": [record["metadata"] for _record_id, record in matched],
        }

    def delete(self, ids):
        for record_id in ids:
            self.records.pop(record_id, None)

    def similarity_search_with_score(self, query, k):
        self.last_search = (query, k)
        return self.search_results[:k]


@override_settings(DOCUMENT_CHUNK_SIZE=30, DOCUMENT_CHUNK_OVERLAP=5)
class IndexingServiceTests(SimpleTestCase):
    def setUp(self):
        self.store = FakeVectorStore()
        self.vector_store_patch = patch(
            "documents.services.indexing.get_vector_store", return_value=self.store
        )
        self.vector_store_patch.start()
        self.addCleanup(self.vector_store_patch.stop)

    def test_indexing_uses_deterministic_ids_metadata_and_unicode_text(self):
        document = SimpleNamespace(
            pk=7,
            title="گزارش شرکت",
            content="این متن فارسی بدون تغییر باقی می‌ماند.\n\nSecond paragraph.",
        )

        chunk_count = indexing.index_document(document)

        self.assertGreater(chunk_count, 1)
        self.assertEqual(
            list(self.store.records),
            [f"document-7-chunk-{index}" for index in range(chunk_count)],
        )
        for index, record in enumerate(self.store.records.values()):
            self.assertEqual(
                record["metadata"],
                {
                    "document_id": 7,
                    "document_title": "گزارش شرکت",
                    "chunk_index": index,
                },
            )
        self.assertIn("فارسی", " ".join(r["text"] for r in self.store.records.values()))

    def test_file_replacement_removes_all_old_chunks_before_reindexing(self):
        document = SimpleNamespace(
            pk=8,
            title="Employees",
            content="Old content " * 20,
        )
        indexing.index_document(document)
        self.assertGreater(len(self.store.records), 1)

        document.content = "New fact: 250 employees."
        indexing.index_document(document)

        self.assertEqual(list(self.store.records), ["document-8-chunk-0"])
        indexed_text = " ".join(r["text"] for r in self.store.records.values())
        self.assertIn("250 employees", indexed_text)
        self.assertNotIn("Old content", indexed_text)

    def test_title_update_changes_metadata_without_reembedding(self):
        document = SimpleNamespace(pk=9, title="Old title", content="Stable text")
        indexing.index_document(document)
        add_calls = self.store.add_calls

        document.title = "New title"
        updated_count = indexing.update_document_title(document)

        self.assertEqual(updated_count, 1)
        self.assertEqual(self.store.add_calls, add_calls)
        self.assertEqual(
            self.store.records["document-9-chunk-0"]["metadata"]["document_title"],
            "New title",
        )

    def test_delete_removes_every_record_without_orphans(self):
        document = SimpleNamespace(pk=10, title="Delete", content="Chunk " * 20)
        indexing.index_document(document)

        indexing.delete_document_index(document.pk)

        self.assertEqual(self.store.records, {})


class E5EmbeddingsTests(SimpleTestCase):
    def test_passage_and_query_prefixes_are_only_applied_at_embedding_boundary(self):
        delegate = Mock()
        delegate.embed_documents.return_value = [[1.0, 0.0]]
        delegate.embed_query.return_value = [1.0, 0.0]
        embeddings = indexing.E5Embeddings(delegate)

        embeddings.embed_documents(["متن اصلی"])
        embeddings.embed_query("پرسش کاربر")

        delegate.embed_documents.assert_called_once_with(["passage: متن اصلی"])
        delegate.embed_query.assert_called_once_with("query: پرسش کاربر")


class RetrievalServiceTests(SimpleTestCase):
    def test_search_returns_original_text_and_source_metadata(self):
        store = FakeVectorStore()
        store.search_results = [
            (
                LangChainDocument(
                    page_content="تعداد کارکنان شرکت ۱۲۰ نفر است.",
                    metadata={
                        "document_id": 1,
                        "document_title": "گزارش شرکت",
                        "chunk_index": 2,
                    },
                ),
                0.25,
            )
        ]

        with patch(
            "documents.services.retrieval.get_vector_store", return_value=store
        ):
            results = retrieval.search_documents("  چند کارمند؟  ", top_k=3)

        self.assertEqual(store.last_search, ("چند کارمند؟", 3))
        self.assertEqual(
            results,
            [
                {
                    "text": "تعداد کارکنان شرکت ۱۲۰ نفر است.",
                    "document_id": 1,
                    "document_title": "گزارش شرکت",
                    "chunk_index": 2,
                    "distance": 0.25,
                }
            ],
        )


class SearchApiTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("document-search")

    def test_empty_query_is_rejected(self):
        for query in ("", "   "):
            response = self.client.post(self.url, {"query": query}, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("query", response.data)

    def test_query_must_be_a_string(self):
        response = self.client.post(self.url, {"query": 123}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("query", response.data)

    def test_invalid_top_k_is_rejected(self):
        for top_k in (0, 21, "4", True):
            response = self.client.post(
                self.url, {"query": "valid", "top_k": top_k}, format="json"
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("top_k", response.data)

    @patch("documents.views.search_documents", return_value=[])
    def test_default_top_k_is_four(self, search_documents):
        response = self.client.post(
            self.url, {"query": "  نیروی انسانی  "}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"query": "نیروی انسانی", "results": []})
        search_documents.assert_called_once_with("نیروی انسانی", top_k=4)


class KeywordEmbeddings(Embeddings):
    """Tiny deterministic test embedding boundary; it never downloads a model."""

    @staticmethod
    def _embed(text):
        employee_words = ("کارمند", "کارکنان", "نیروی انسانی", "نفر")
        location_words = ("دفتر", "مقر", "تهران", "کجاست")
        if any(word in text for word in employee_words):
            return [1.0, 0.0, 0.0]
        if any(word in text for word in location_words):
            return [0.0, 1.0, 0.0]
        return [0.0, 0.0, 1.0]

    def embed_documents(self, texts):
        return [self._embed(text) for text in texts]

    def embed_query(self, text):
        return self._embed(text)


@override_settings(DOCUMENT_CHUNK_SIZE=80, DOCUMENT_CHUNK_OVERLAP=10)
class PersianChromaIntegrationTests(SimpleTestCase):
    def test_representative_persian_query_returns_relevant_persistent_chunk(self):
        with tempfile.TemporaryDirectory() as persist_directory:
            vector_store = Chroma(
                collection_name=f"test_documents_{uuid4().hex}",
                embedding_function=indexing.E5Embeddings(KeywordEmbeddings()),
                persist_directory=persist_directory,
            )
            document = SimpleNamespace(
                pk=11,
                title="شرکت آریا",
                content=(
                    "دفتر مرکزی شرکت در تهران قرار دارد.\n\n"
                    "در حال حاضر شرکت آریا ۱۲۰ نفر کارمند دارد.\n\n"
                    "محصول اصلی شرکت سامانه منابع انسانی ابری است."
                ),
            )

            with patch(
                "documents.services.indexing.get_vector_store",
                return_value=vector_store,
            ):
                indexing.index_document(document)
                stored = vector_store.get(where={"document_id": 11})

            with patch(
                "documents.services.retrieval.get_vector_store",
                return_value=vector_store,
            ):
                results = retrieval.search_documents(
                    "نیروی انسانی مجموعه چند نفر است؟", top_k=1
                )

            self.assertTrue(stored["ids"])
            self.assertIn("۱۲۰ نفر کارمند", results[0]["text"])
            self.assertEqual(results[0]["document_title"], "شرکت آریا")
