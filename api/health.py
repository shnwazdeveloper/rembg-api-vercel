from http.server import BaseHTTPRequestHandler

from lib.rembg_api import send_json, send_options


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        send_options(self)

    def do_GET(self):
        send_json(self, 200, {"status": "ok"})
