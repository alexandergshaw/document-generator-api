"""Generator registry.

Maps a requested output document type to the module that produces it. Every
generator implements the same tiny contract::

    generate(template_bytes: bytes, content: dict) -> bytes

`app.py` looks up the requested format here and dispatches to it. Adding a new
output format is a two-step job: write a `generate()` in a new module, then add
one row to ``REGISTRY`` below.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from . import text, docx_gen, pptx_gen, xlsx_gen, pdf_gen


@dataclass(frozen=True)
class Format:
    """Everything the app needs to know about one output format."""

    name: str
    mime: str
    extension: str
    generate: Callable[[bytes, dict], bytes]
    # True when the template MUST arrive as an uploaded binary file (Office
    # formats); False when a raw text template may be pasted instead.
    requires_template: bool = False
    description: str = ""


REGISTRY: dict[str, Format] = {
    "txt": Format(
        "txt", "text/plain; charset=utf-8", "txt",
        text.generate, False, "Plain text rendered with Jinja2",
    ),
    "md": Format(
        "md", "text/markdown; charset=utf-8", "md",
        text.generate, False, "Markdown rendered with Jinja2",
    ),
    "html": Format(
        "html", "text/html; charset=utf-8", "html",
        text.generate, False, "HTML rendered with Jinja2",
    ),
    "csv": Format(
        "csv", "text/csv; charset=utf-8", "csv",
        text.generate, False, "CSV rendered with Jinja2",
    ),
    "docx": Format(
        "docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "docx", docx_gen.generate, True,
        "Word document from a .docx template (docxtpl)",
    ),
    "pptx": Format(
        "pptx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "pptx", pptx_gen.generate, True,
        "PowerPoint from a .pptx template (python-pptx)",
    ),
    "xlsx": Format(
        "xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xlsx", xlsx_gen.generate, True,
        "Excel workbook from a .xlsx template (openpyxl)",
    ),
    "pdf": Format(
        "pdf", "application/pdf", "pdf",
        pdf_gen.generate, False,
        "PDF from an HTML template (xhtml2pdf)",
    ),
}


def get_format(name: str) -> Format | None:
    """Return the Format for ``name`` (case-insensitive), or None."""
    if not name:
        return None
    return REGISTRY.get(name.strip().lower())


def supported_formats() -> list[dict]:
    """Serializable list of formats for the /api/formats endpoint and the UI."""
    return [
        {
            "name": f.name,
            "extension": f.extension,
            "requires_template": f.requires_template,
            "description": f.description,
        }
        for f in REGISTRY.values()
    ]
