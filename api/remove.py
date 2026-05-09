from http.server import BaseHTTPRequestHandler

from lib.rembg_api import APIError, handle_remove, send_error_json, send_options


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        send_options(self)

    def do_GET(self):
        self._remove_background()

    def do_POST(self):
        self._remove_background()

    def _remove_background(self):
        try:
            handle_remove(self)
        except APIError as exc:
            send_error_json(self, exc.status, exc.message)
        except Exception as exc:
            send_error_json(self, 500, f"Background removal failed: {exc}")
