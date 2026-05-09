import base64
import binascii
import ipaddress
import json
import os
import socket
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler
from typing import Any
from urllib.parse import parse_qs, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


MAX_IMAGE_BYTES = int(os.getenv("MAX_IMAGE_BYTES", str(8 * 1024 * 1024)))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "15"))
DEFAULT_MODEL = os.getenv("REMBG_MODEL", "u2netp")
ALLOWED_MODELS = {
    model.strip()
    for model in os.getenv("ALLOWED_MODELS", "u2netp,silueta").split(",")
    if model.strip()
}

_SESSIONS: dict[str, Any] = {}


class APIError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def send_options(handler: BaseHTTPRequestHandler) -> None:
    handler.send_response(204)
    _send_cors_headers(handler)
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.end_headers()


def send_json(
    handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]
) -> None:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    handler.send_response(status)
    _send_cors_headers(handler)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def send_error_json(handler: BaseHTTPRequestHandler, status: int, message: str) -> None:
    send_json(handler, status, {"error": message})


def handle_remove(handler: BaseHTTPRequestHandler) -> None:
    image_bytes, options = _extract_request(handler)
    output = remove_background(image_bytes, options)

    handler.send_response(200)
    _send_cors_headers(handler)
    handler.send_header("Content-Type", "image/png")
    handler.send_header("Content-Disposition", 'inline; filename="rembg-output.png"')
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(output)))
    handler.end_headers()
    handler.wfile.write(output)


def remove_background(image_bytes: bytes, options: dict[str, Any]) -> bytes:
    if not image_bytes:
        raise APIError(400, "No image data received.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise APIError(413, f"Image is larger than {MAX_IMAGE_BYTES} bytes.")

    model = str(options.get("model") or DEFAULT_MODEL).strip()
    if model not in ALLOWED_MODELS:
        raise APIError(
            400,
            f"Model '{model}' is not allowed. Allowed models: {', '.join(sorted(ALLOWED_MODELS))}.",
        )

    os.environ.setdefault("U2NET_HOME", "/tmp/rembg-models")
    os.environ.setdefault("OMP_NUM_THREADS", "1")

    from rembg import new_session, remove

    session = _SESSIONS.get(model)
    if session is None:
        session = new_session(model)
        _SESSIONS[model] = session

    result = remove(
        image_bytes,
        session=session,
        alpha_matting=_as_bool(options.get("alpha_matting")),
        only_mask=_as_bool(options.get("only_mask")),
        post_process_mask=_as_bool(options.get("post_process_mask")),
        force_return_bytes=True,
    )
    if not isinstance(result, bytes):
        raise APIError(500, "Unexpected rembg output type.")
    return result


def _extract_request(handler: BaseHTTPRequestHandler) -> tuple[bytes, dict[str, Any]]:
    query = parse_qs(urlparse(handler.path).query)
    query_options = _flatten_query(query)

    if handler.command == "GET":
        url = query_options.get("url")
        if not url:
            raise APIError(400, "Pass an image URL with /api/remove?url=...")
        return _download_image(str(url)), query_options

    content_length = int(handler.headers.get("Content-Length", "0") or "0")
    if content_length <= 0:
        raise APIError(400, "Request body is empty.")
    if content_length > MAX_IMAGE_BYTES * 2:
        raise APIError(413, "Request body is too large.")

    content_type = handler.headers.get("Content-Type", "")
    body = handler.rfile.read(content_length)

    if "multipart/form-data" in content_type:
        image_bytes, fields = _parse_multipart(content_type, body)
        fields.update(query_options)
        return image_bytes, fields

    if "application/json" in content_type:
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise APIError(400, f"Invalid JSON: {exc}") from exc

        if not isinstance(payload, dict):
            raise APIError(400, "JSON body must be an object.")

        options = {**payload, **query_options}
        if payload.get("url"):
            return _download_image(str(payload["url"])), options
        encoded = payload.get("image_base64") or payload.get("image")
        if encoded:
            return _decode_base64_image(str(encoded)), options
        raise APIError(400, "JSON must include image_base64, image, or url.")

    if "application/x-www-form-urlencoded" in content_type:
        form = _flatten_query(parse_qs(body.decode("utf-8"), keep_blank_values=True))
        options = {**form, **query_options}
        url = form.get("url")
        if not url:
            raise APIError(400, "Form body must include url=...")
        return _download_image(str(url)), options

    if content_type.startswith("image/") or content_type == "application/octet-stream":
        return body, query_options

    raise APIError(
        415,
        "Unsupported content type. Use multipart/form-data, application/json, application/x-www-form-urlencoded, or raw image bytes.",
    )


def _parse_multipart(content_type: str, body: bytes) -> tuple[bytes, dict[str, Any]]:
    raw = (
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
        + body
    )
    message = BytesParser(policy=default).parsebytes(raw)
    if not message.is_multipart():
        raise APIError(400, "Invalid multipart request.")

    fields: dict[str, Any] = {}
    image_bytes = b""

    for part in message.iter_parts():
        disposition = part.get("Content-Disposition", "")
        if "form-data" not in disposition:
            continue

        name = part.get_param("name", header="content-disposition")
        filename = part.get_param("filename", header="content-disposition")
        payload = part.get_payload(decode=True) or b""

        if filename or name in {"file", "image", "upload"}:
            image_bytes = payload
        elif name:
            fields[str(name)] = payload.decode("utf-8", errors="replace")

    if not image_bytes:
        raise APIError(400, "Multipart form must include a file field.")
    return image_bytes, fields


def _download_image(url: str) -> bytes:
    _validate_public_url(url)
    opener = build_opener(_SafeRedirectHandler)
    request = Request(url, headers={"User-Agent": "rembg-api-vercel/1.0"})

    with opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        content_type = response.headers.get("Content-Type", "")
        if not content_type.startswith("image/"):
            raise APIError(415, f"URL did not return an image. Content-Type: {content_type}")

        data = response.read(MAX_IMAGE_BYTES + 1)
        if len(data) > MAX_IMAGE_BYTES:
            raise APIError(413, f"Remote image is larger than {MAX_IMAGE_BYTES} bytes.")
        return data


def _validate_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise APIError(400, "Only http and https image URLs are supported.")
    if not parsed.hostname:
        raise APIError(400, "Image URL must include a hostname.")

    try:
        infos = socket.getaddrinfo(parsed.hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise APIError(400, f"Could not resolve image URL hostname: {parsed.hostname}") from exc

    for info in infos:
        address = info[4][0]
        ip = ipaddress.ip_address(address)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise APIError(400, "Private or local image URLs are not allowed.")


def _decode_base64_image(value: str) -> bytes:
    encoded = value.split(",", 1)[1] if value.startswith("data:") else value
    try:
        return base64.b64decode(encoded, validate=True)
    except binascii.Error as exc:
        raise APIError(400, "Invalid base64 image data.") from exc


def _flatten_query(query: dict[str, list[str]]) -> dict[str, Any]:
    return {key: values[-1] for key, values in query.items() if values}


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _send_cors_headers(handler: BaseHTTPRequestHandler) -> None:
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Vary", "Origin")
