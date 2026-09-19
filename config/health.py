import chromadb
from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_safe
from django.views.decorators.cache import never_cache


def _database_is_ready() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return False
    return True


def _vector_store_is_ready() -> bool:
    try:
        client = chromadb.PersistentClient(
            path=str(settings.CHROMA_PERSIST_DIRECTORY)
        )
        client.heartbeat()
    except Exception:
        return False
    return True


@never_cache
@require_safe
def live(_request):
    return JsonResponse({"status": "ok"})


@never_cache
@require_safe
def ready(_request):
    checks = {
        "database": "ok" if _database_is_ready() else "error",
        "vector_store": "ok" if _vector_store_is_ready() else "error",
    }
    is_ready = all(result == "ok" for result in checks.values())
    return JsonResponse(
        {
            "status": "ready" if is_ready else "unavailable",
            "checks": checks,
        },
        status=200 if is_ready else 503,
    )
