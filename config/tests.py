from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse


class HealthEndpointTests(TestCase):
    def setUp(self):
        self.live_url = reverse("health-live")
        self.ready_url = reverse("health-ready")

    @patch("config.health.chromadb.PersistentClient")
    @patch("config.health.connection.cursor")
    def test_liveness_is_ok_without_dependency_checks(
        self, database_cursor, persistent_client
    ):
        response = self.client.get(self.live_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        database_cursor.assert_not_called()
        persistent_client.assert_not_called()

    @patch("config.health.chromadb.PersistentClient")
    def test_healthy_readiness(self, persistent_client):
        persistent_client.return_value.heartbeat.return_value = 1

        response = self.client.get(self.ready_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "ready",
                "checks": {"database": "ok", "vector_store": "ok"},
            },
        )
        persistent_client.return_value.heartbeat.assert_called_once_with()

    @patch("config.health.chromadb.PersistentClient")
    @patch(
        "config.health.connection.cursor",
        side_effect=RuntimeError("private database detail"),
    )
    def test_database_failure_is_sanitized(
        self, _database_cursor, persistent_client
    ):
        response = self.client.get(self.ready_url)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["checks"]["database"], "error")
        self.assertEqual(response.json()["checks"]["vector_store"], "ok")
        self.assertNotContains(
            response, "private database detail", status_code=503
        )
        persistent_client.return_value.heartbeat.assert_called_once_with()

    @patch(
        "config.health.chromadb.PersistentClient",
        side_effect=RuntimeError("private vector-store detail"),
    )
    def test_vector_store_failure_is_sanitized(self, _persistent_client):
        response = self.client.get(self.ready_url)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["checks"]["database"], "ok")
        self.assertEqual(response.json()["checks"]["vector_store"], "error")
        self.assertNotContains(
            response, "private vector-store detail", status_code=503
        )

    @patch("config.health.chromadb.PersistentClient")
    def test_head_is_supported(self, persistent_client):
        live_response = self.client.head(self.live_url)
        ready_response = self.client.head(self.ready_url)

        self.assertEqual(live_response.status_code, 200)
        self.assertEqual(live_response.content, b"")
        self.assertEqual(ready_response.status_code, 200)
        self.assertEqual(ready_response.content, b"")

    def test_post_is_rejected(self):
        self.assertEqual(self.client.post(self.live_url).status_code, 405)
        self.assertEqual(self.client.post(self.ready_url).status_code, 405)
