"""PDF generator.

Treats the uploaded (or pasted) template as an HTML document, renders it with
Jinja2, then converts the HTML to PDF with xhtml2pdf (pure-Python, no system
binaries — so the project installs with a single ``pip install`` on Windows).

For higher CSS fidelity, swap in WeasyPrint (needs GTK on Windows); to produce a
PDF that matches a Word/PowerPoint template exactly, fill the Office template
first and convert with LibreOffice headless or docx2pdf. See README.
"""
from __future__ import annotations

from io import BytesIO

from xhtml2pdf import pisa

from ._jinja import make_env, resolve_strict

_DEFAULT_STRICT = True


def generate(template_bytes: bytes, content: dict, strict=None) -> bytes:
    env = make_env(resolve_strict(strict, _DEFAULT_STRICT))
    html = env.from_string(template_bytes.decode("utf-8")).render(**content)
    out = BytesIO()
    result = pisa.CreatePDF(src=html, dest=out, encoding="utf-8")
    if result.err:
        raise ValueError(f"PDF conversion failed with {result.err} error(s)")
    return out.getvalue()
