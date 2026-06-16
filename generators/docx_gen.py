"""DOCX generator.

Fills an uploaded .docx template using docxtpl, which understands Jinja2 syntax
(``{{ var }}``, ``{% for %}``, conditionals, images) placed directly inside the
Word document. docxtpl manages its own Jinja environment so that the rendered
text is correctly XML-escaped; we let it use those defaults.
"""
from __future__ import annotations

from io import BytesIO

from docxtpl import DocxTemplate


def generate(template_bytes: bytes, content: dict) -> bytes:
    doc = DocxTemplate(BytesIO(template_bytes))
    doc.render(content)
    out = BytesIO()
    doc.save(out)
    return out.getvalue()
