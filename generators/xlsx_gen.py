"""XLSX generator.

Loads an uploaded .xlsx template and renders every string cell that contains a
Jinja2 marker (``{{`` or ``{%``) against the supplied content. Cells without a
marker are left untouched, so existing formatting, formulas and layout survive.
"""
from __future__ import annotations

from io import BytesIO

from jinja2 import BaseLoader, Environment, StrictUndefined
from openpyxl import load_workbook

_env = Environment(loader=BaseLoader(), undefined=StrictUndefined, autoescape=False)


def _has_marker(value: str) -> bool:
    return "{{" in value or "{%" in value


def generate(template_bytes: bytes, content: dict) -> bytes:
    wb = load_workbook(BytesIO(template_bytes))
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and _has_marker(cell.value):
                    cell.value = _env.from_string(cell.value).render(**content)
    out = BytesIO()
    wb.save(out)
    return out.getvalue()
