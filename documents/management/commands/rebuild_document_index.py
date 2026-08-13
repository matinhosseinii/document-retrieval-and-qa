from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from documents.models import Document
from documents.services.indexing import (
    get_vector_store,
    index_document,
    split_document_content,
)


class Command(BaseCommand):
    help = "Rebuild the configured Chroma collection from SQLite Document.content."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Clear only the configured target collection before rebuilding.",
        )

    def handle(self, *args, **options):
        documents = list(Document.objects.all().order_by("pk"))
        expected_chunks = sum(
            len(split_document_content(document.content)) for document in documents
        )
        self.stdout.write(f"Target collection: {settings.CHROMA_COLLECTION_NAME}")
        self.stdout.write(f"SQLite documents: {len(documents)}")
        self.stdout.write(f"Expected chunks: {expected_chunks}")

        vector_store = get_vector_store()
        existing_ids = list(vector_store.get().get("ids", []))
        self.stdout.write(f"Existing target records: {len(existing_ids)}")

        if existing_ids and not options["force"]:
            raise CommandError(
                "The configured target collection is not empty. "
                "Use --force to clear only this collection and rebuild it."
            )
        if existing_ids:
            vector_store.delete(ids=existing_ids)
            self.stdout.write(
                f"Cleared {len(existing_ids)} records from the configured collection."
            )

        processed = 0
        indexed = 0
        failures = []
        for document in documents:
            try:
                indexed += index_document(document)
                processed += 1
            except Exception as exc:
                failures.append((document.pk, exc))
                self.stderr.write(f"Document {document.pk} failed: {exc}")
                break

        actual_chunks = len(get_vector_store().get().get("ids", []))
        self.stdout.write(f"Documents processed: {processed}")
        self.stdout.write(f"Chunks expected: {expected_chunks}")
        self.stdout.write(f"Chunks indexed: {actual_chunks}")
        self.stdout.write(f"Failures: {len(failures)}")

        if failures or processed != len(documents) or actual_chunks != expected_chunks:
            raise CommandError("Index rebuild is incomplete; the target was not validated.")
        if indexed != expected_chunks:
            raise CommandError("Indexing returned an unexpected chunk count.")

        self.stdout.write(self.style.SUCCESS("Configured collection rebuilt successfully."))
