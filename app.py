"""Document Generator — Flask API + test UI.

A caller supplies an output *document type*, a *template* (uploaded formatted
file, or pasted text for text/PDF formats) and *content* (a JSON object). The
matching generator fills the template and the rendered document is streamed back
as a download.
"""
from __future__ import annotations

import json
from io import BytesIO

from flask import Flask, jsonify, render_template, request, send_file

from generators import REGISTRY, get_format, supported_formats

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB upload cap


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/formats")
def formats():
    return jsonify({"formats": supported_formats()})


@app.post("/api/generate")
def generate():
    # 1. Output format
    doc_type = (request.form.get("document_type") or "").strip().lower()
    fmt = get_format(doc_type)
    if fmt is None:
        supported = ", ".join(sorted(REGISTRY))
        return jsonify(
            {"error": f"Unsupported document_type '{doc_type}'. Supported: {supported}"}
        ), 400

    # 2. Content (JSON object)
    raw_content = (request.form.get("content") or "").strip() or "{}"
    try:
        content = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        return jsonify({"error": f"content is not valid JSON: {exc}"}), 400
    if not isinstance(content, dict):
        return jsonify({"error": "content must be a JSON object (key/value pairs)"}), 400

    # 3. Template — uploaded file, or pasted text for non-binary formats
    template_bytes: bytes | None = None
    upload = request.files.get("template")
    if upload and upload.filename:
        template_bytes = upload.read()
    elif request.form.get("template_text"):
        template_bytes = request.form["template_text"].encode("utf-8")

    if not template_bytes:
        if fmt.requires_template:
            return jsonify(
                {"error": f"'{doc_type}' requires an uploaded template file."}
            ), 400
        return jsonify(
            {"error": "No template provided. Upload a file or supply 'template_text'."}
        ), 400

    # 4. Generate
    try:
        data = fmt.generate(template_bytes, content)
    except Exception as exc:  # surface generation/render errors to the caller
        return jsonify({"error": f"Generation failed: {exc}"}), 500

    # 5. Stream back as a download
    download_name = _download_name(request.form.get("filename"), fmt.extension)
    return send_file(
        BytesIO(data),
        mimetype=fmt.mime.split(";")[0],
        as_attachment=True,
        download_name=download_name,
    )


def _download_name(requested: str | None, extension: str) -> str:
    if not requested:
        return f"document.{extension}"
    requested = requested.strip()
    if requested.lower().endswith(f".{extension}"):
        return requested
    return f"{requested}.{extension}"


if __name__ == "__main__":
    app.run(debug=True, port=5000)
