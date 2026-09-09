import tempfile
import unittest
from pathlib import Path

from starlette.requests import Request
from starlette.responses import Response

from app.application import create_app
from app.build_profile import DeploymentMode
from app.config import ApplicationSettings
from app.database import create_db_and_tables
from app.routers.health import liveness, metrics, readiness


class OperationsEndpointTests(unittest.TestCase):
    def test_health_metrics_and_request_ids_are_available(self):
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory)
            settings = ApplicationSettings.model_validate(
                {
                    "database": {
                        "url": (
                            "sqlite:///"
                            + (data_path / "notes.db").as_posix()
                        )
                    },
                    "storage": {"path": str(data_path)},
                    "server": {"open_browser": False},
                }
            )
            application = create_app(
                settings,
                build_profile=DeploymentMode.LOCAL,
            )
            engine = create_db_and_tables(settings)
            try:
                live_response = Response()
                live = liveness(live_response)
                ready_response = Response()
                ready = readiness(ready_response)
                application.state.request_metrics.begin()
                application.state.request_metrics.finish(200, 0.01)
                request = Request(
                    {
                        "type": "http",
                        "app": application,
                        "method": "GET",
                        "path": "/metrics",
                        "headers": [],
                    }
                )
                metrics_response = metrics(request)
            finally:
                engine.dispose()

            self.assertEqual({"status": "ok"}, live)
            self.assertEqual(
                "no-store",
                live_response.headers["Cache-Control"],
            )

            self.assertEqual({"status": "ready"}, ready)
            self.assertEqual(200, ready_response.status_code)

            self.assertEqual(200, metrics_response.status_code)
            self.assertIn(
                "dnd_notes_http_requests_total",
                metrics_response.body.decode("utf-8"),
            )
            self.assertEqual(
                "no-store",
                metrics_response.headers["Cache-Control"],
            )

    def test_operations_routes_do_not_use_the_authenticated_api_prefix(self):
        application = create_app(
            ApplicationSettings(),
            build_profile=DeploymentMode.LOCAL,
        )
        paths = set(application.openapi()["paths"])
        self.assertIn("/health/live", paths)
        self.assertIn("/health/ready", paths)
        self.assertIn("/metrics", paths)
        self.assertNotIn("/api/health/live", paths)


if __name__ == "__main__":
    unittest.main()
