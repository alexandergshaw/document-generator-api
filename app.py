"""Document Generator — Flask API + test UI.

A generic template renderer with multiple consumers. A caller supplies an output
*document type*, a *template* (uploaded file, or pasted text for text/PDF
formats) and *content* (a JSON object); the matching generator fills the
template and the rendered document is streamed back as a download.

This service deliberately contains **no document-domain logic** — it is a plain
template+content renderer. See README for the request contract, error codes,
strictness matrix and deployment notes.
"""
from __future__ import annotations

import json
import os
import re
from io import BytesIO

from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from generators import REGISTRY, get_format, supported_formats

# Semantic version of the API contract. Consumers can pin to this (exposed via
# /api/health and /api/formats). Bump on contract changes.
API_VERSION = "1.0.0"

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB request cap
app.config["API_VERSION"] = API_VERSION


def _split_csv(raw: str | None) -> list[str]:
    return [item.strip() for item in (raw or "").split(",") if item.strip()]


# Env-gated config. Deploys set the env vars; tests can override app.config.
app.config["API_KEY"] = os.environ.get("API_KEY") or None
app.config["ALLOWED_ORIGINS"] = _split_csv(os.environ.get("ALLOWED_ORIGINS"))


# --- helpers ---------------------------------------------------------------

def _error(message: str, code: str, status: int):
    """Uniform JSON error envelope: ``{"error": ..., "code": ...}``."""
    return jsonify({"error": message, "code": code}), status


_BOOL_TRUE = {"1", "true", "yes", "on"}
_BOOL_FALSE = {"0", "false", "no", "off"}


def _parse_bool(raw: str | None):
    """Tri-state parse: True / False / None (unset or unrecognized)."""
    if raw is None:
        return None
    value = raw.strip().lower()
    if value in _BOOL_TRUE:
        return True
    if value in _BOOL_FALSE:
        return False
    return None


def _allowed_origin(origin: str | None) -> str | None:
    """Return the Origin to echo back, or None if CORS isn't allowed for it."""
    allowed = app.config.get("ALLOWED_ORIGINS") or []
    if not origin or not allowed:
        return None
    if "*" in allowed:
        return origin
    return origin if origin in allowed else None


# --- CORS (opt-in via ALLOWED_ORIGINS) -------------------------------------

@app.after_request
def _apply_cors(response):
    origin = _allowed_origin(request.headers.get("Origin"))
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-API-Key"
    return response


# --- error handlers: every error returns the JSON envelope -----------------

@app.errorhandler(RequestEntityTooLarge)
def _handle_too_large(_exc):
    return _error("Request exceeds the 16 MB size limit.", "too_large", 413)


@app.errorhandler(HTTPException)
def _handle_http_exception(exc: HTTPException):
    # Framework defaults (404, 405, …) also return JSON instead of HTML.
    code = (exc.name or "error").lower().replace(" ", "_")
    return _error(exc.description or exc.name or "Error", code, exc.code or 500)


# --- routes ----------------------------------------------------------------

@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "version": app.config["API_VERSION"]})


@app.get("/api/formats")
def formats():
    return jsonify(
        {"version": app.config["API_VERSION"], "formats": supported_formats()}
    )


@app.post("/api/generate")
def generate():
    # 0. Optional auth — enforced only when API_KEY is configured.
    api_key = app.config.get("API_KEY")
    if api_key and request.headers.get("X-API-Key") != api_key:
        return _error("Missing or invalid API key.", "unauthorized", 401)

    # 1. Output format
    doc_type = (request.form.get("document_type") or "").strip().lower()
    fmt = get_format(doc_type)
    if fmt is None:
        supported = ", ".join(sorted(REGISTRY))
        return _error(
            f"Unsupported document_type '{doc_type}'. Supported: {supported}",
            "unsupported_type", 400,
        )

    # 2. Content (JSON object)
    raw_content = (request.form.get("content") or "").strip() or "{}"
    try:
        content = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        return _error(f"content is not valid JSON: {exc}", "invalid_json", 400)
    if not isinstance(content, dict):
        return _error(
            "content must be a JSON object (key/value pairs)",
            "content_not_object", 400,
        )

    # 3. Optional missing-key strictness (tri-state; None -> per-format default)
    strict = _parse_bool(request.form.get("strict"))

    # 4. Template — uploaded file takes precedence over pasted text
    template_bytes: bytes | None = None
    upload = request.files.get("template")
    if upload and upload.filename:
        template_bytes = upload.read()
    elif request.form.get("template_text"):
        template_bytes = request.form["template_text"].encode("utf-8")

    if not template_bytes:
        if fmt.requires_template:
            return _error(
                f"'{doc_type}' requires an uploaded template file.",
                "template_required", 400,
            )
        return _error(
            "No template provided. Upload a file or supply 'template_text'.",
            "no_template", 400,
        )

    # 5. Generate
    try:
        data = fmt.generate(template_bytes, content, strict)
    except Exception as exc:  # surface render/generation errors to the caller
        return _error(f"Generation failed: {exc}", "render_failed", 500)

    # 6. Stream back as a download
    download_name = _download_name(request.form.get("filename"), fmt.extension)
    return send_file(
        BytesIO(data),
        mimetype=fmt.mime.split(";")[0],
        as_attachment=True,
        download_name=download_name,
    )


def _download_name(requested: str | None, extension: str) -> str:
    """Sanitize a caller-supplied download name and ensure the right extension.

    Strips directory components, path traversal, control characters and
    filesystem-illegal characters, then appends the format's extension.
    """
    fallback = f"document.{extension}"
    if not requested:
        return fallback
    # Keep only the final path component (drops dirs and ../ traversal).
    name = requested.strip().replace("\\", "/").split("/")[-1]
    # Remove control characters and characters illegal in filenames.
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    # Strip leading/trailing dots and spaces (also neutralizes "..").
    name = name.strip(". ")
    if not name:
        return fallback
    if name.lower().endswith(f".{extension}"):
        return name
    return f"{name}.{extension}"


if __name__ == "__main__":
    # Development server only. For production, run under a real WSGI server:
    #   waitress-serve --port=5000 app:app     (Windows)
    #   gunicorn -w 4 app:app                   (Linux/macOS)
    debug = _parse_bool(os.environ.get("DEBUG")) or False
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=debug)
