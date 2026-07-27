import unittest

from starlette.requests import Request

from app.config import RequestLimitSettings
from app.request_limits import (
    FixedWindowRateLimiter,
    classify_limited_request,
)


def request(
    method: str,
    path: str,
    content_type: str | None = None,
) -> Request:
    headers = []
    if content_type:
        headers.append((b"content-type", content_type.encode("ascii")))
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "headers": headers,
            "client": ("192.0.2.10", 12345),
            "scheme": "https",
            "server": ("notes.example.test", 443),
        }
    )


class RequestLimitTests(unittest.TestCase):
    def test_fixed_window_blocks_and_resets(self):
        now = [100.0]
        limiter = FixedWindowRateLimiter(
            window_seconds=60,
            clock=lambda: now[0],
        )

        self.assertEqual((True, 0), limiter.consume("search", "ip", 2))
        self.assertEqual((True, 0), limiter.consume("search", "ip", 2))
        allowed, retry_after = limiter.consume("search", "ip", 2)
        self.assertFalse(allowed)
        self.assertEqual(60, retry_after)

        now[0] += 60
        self.assertEqual((True, 0), limiter.consume("search", "ip", 2))

    def test_categories_match_expensive_routes_only(self):
        settings = RequestLimitSettings()
        cases = [
            (
                request("POST", "/api/campaigns/2/search"),
                ("search", settings.search_per_minute),
            ),
            (
                request("POST", "/api/campaigns/backup/import"),
                ("import", settings.import_per_minute),
            ),
            (
                request("GET", "/api/campaigns/2/backup/export"),
                ("export", settings.export_per_minute),
            ),
            (
                request(
                    "PUT",
                    "/api/campaigns/2/characters/4/image",
                    "multipart/form-data; boundary=test",
                ),
                ("upload", settings.upload_per_minute),
            ),
            (request("GET", "/api/campaigns/2"), None),
        ]
        for candidate, expected in cases:
            with self.subTest(path=candidate.url.path):
                self.assertEqual(
                    expected,
                    classify_limited_request(candidate, settings),
                )


if __name__ == "__main__":
    unittest.main()
