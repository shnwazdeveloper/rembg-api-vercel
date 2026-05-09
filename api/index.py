from pathlib import Path
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse

from lib.rembg_api import (
    APIError,
    get_model_metadata,
    handle_remove,
    send_error_json,
    send_json,
    send_options,
)

STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/docs": ("docs/index.html", "text/html; charset=utf-8"),
    "/docs/": ("docs/index.html", "text/html; charset=utf-8"),
    "/docs/index.html": ("docs/index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/assets/sample-before.jpg": ("assets/sample-before.jpg", "image/jpeg"),
    "/assets/sample-after.png": ("assets/sample-after.png", "image/png"),
}


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        send_options(self)

    def do_HEAD(self):
        if self._serve_static(head_only=True):
            return

        send_error_json(self, 404, "The page could not be found.")

    def do_GET(self):
        path = _normalized_path(self.path)
        if self._serve_static():
            return

        if path.endswith("/health"):
            send_json(self, 200, {"status": "ok"})
            return

        if path in {"/model", "/api/model"}:
            send_json(self, 200, get_model_metadata())
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
                    "GET /model": "Model metadata and supported options",
                    "GET /api/model": "Model metadata and supported options",
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

    def _serve_static(self, head_only=False):
        path = urlparse(self.path).path
        match = STATIC_FILES.get(path)
        if match is None:
            return False

        relative_path, content_type = match
        file_path = Path(__file__).resolve().parent.parent / relative_path
        if not file_path.is_file():
            send_error_json(self, 404, "The page could not be found.")
            return True

        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=0, must-revalidate")
        self.end_headers()
        if not head_only:
            self.wfile.write(body)
        return True


def _normalized_path(path: str) -> str:
    return urlparse(path).path.rstrip("/") or "/"
