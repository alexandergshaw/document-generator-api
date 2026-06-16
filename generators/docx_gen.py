"""DOCX generator.

Fills an uploaded .docx template using docxtpl, which understands Jinja2 syntax
(``{{ var }}``, ``{% for %}``, conditionals, images) placed directly inside the
Word document.

Strictness: docx historically renders an undefined key as blank (docxtpl's
default Jinja environment). When the caller asks for ``strict=true`` we render
with a ``StrictUndefined`` environment so a missing key raises instead. To
repeat content, use a ``{% for %}`` loop over a list variable — not duplicated
placeholders. See README "Repeating content".
"""
from __future__ import annotations

from io import BytesIO

from docxtpl import DocxTemplate
from jinja2 import Environment, StrictUndefined

from ._jinja import resolve_strict

# Historical behavior: docx renders missing keys as blank.
_DEFAULT_STRICT = False


def generate(template_bytes: bytes, content: dict, strict=None) -> bytes:
    doc = DocxTemplate(BytesIO(template_bytes))
    if resolve_strict(strict, _DEFAULT_STRICT):
        # autoescape=True keeps special characters valid inside the docx XML.
        env = Environment(undefined=StrictUndefined, autoescape=True)
        doc.render(content, env)
    else:
        doc.render(content)  # unchanged default path
    out = BytesIO()
    doc.save(out)
    return out.getvalue()
