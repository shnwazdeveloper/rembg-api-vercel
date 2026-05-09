from http.server import BaseHTTPRequestHandler

from lib.rembg_api import send_json, send_options


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        send_options(self)

    def do_GET(self):
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
