from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse

from lib.rembg_api import APIError, handle_remove, send_error_json, send_json, send_options


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        send_options(self)

    def do_GET(self):
        path = _normalized_path(self.path)
        if path.endswith("/health"):
            send_json(self, 200, {"status": "ok"})
            return

        if path.endswith("/remove"):
            self._remove_background()
            return

        send_json(
            self,
            200,
            {
                "name": "rembg-api-vercel",
                "status": "ok",
                "source": "https://github.com/danielgatis/rembg",
                "endpoints": {
                    "GET /api/health": "Health check",
                    "POST /api/remove": "Remove a background from multipart, JSON/base64, URL encoded, or raw image input",
                    "GET /api/remove?url=https://example.com/image.jpg": "Remove a background from a remote image URL",
                },
                "multipart_example": "curl -s -F file=@input.jpg https://your-domain.vercel.app/api/remove -o output.png",
                "json_example": {
                    "method": "POST",
                    "path": "/api/remove",
                    "body": {
                        "image_base64": "data:image/png;base64,...",
                        "model": "u2netp",
                    },
                },
                "models": ["u2netp", "silueta"],
                "default_model": "u2netp",
            },
        )

    def do_POST(self):
        path = _normalized_path(self.path)
        if path.endswith("/remove"):
            self._remove_background()
            return

        send_error_json(self, 404, "Use POST /api/remove to remove a background.")

    def _remove_background(self):
        try:
            handle_remove(self)
        except APIError as exc:
            send_error_json(self, exc.status, exc.message)
        except Exception as exc:
            send_error_json(self, 500, f"Background removal failed: {exc}")


def _normalized_path(path: str) -> str:
    return urlparse(path).path.rstrip("/") or "/api"
