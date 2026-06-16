"""End-to-end tests for the document generator API.

Templates are built in-memory so the suite is self-contained (no dependency on
the samples/ folder having been generated).
"""
import io
import json

import pytest
from docx import Document
from openpyxl import Workbook, load_workbook
from pptx import Presentation

import app as flask_app

CONTENT = {
    "company_name": "Acme Corp",
    "customer_name": "Ada Lovelace",
    "invoice_number": "A-1042",
    "date": "2026-06-15",
    "items": [
        {"name": "Widget", "amount": "$10.00"},
        {"name": "Gadget", "amount": "$25.50"},
    ],
    "total": "$35.50",
}


@pytest.fixture
def client():
    flask_app.app.config.update(TESTING=True)
    return flask_app.app.test_client()


# --- in-memory template builders ------------------------------------------

def _docx_template() -> bytes:
    doc = Document()
    doc.add_paragraph("Invoice {{ invoice_number }} for {{ customer_name }}")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _pptx_template() -> bytes:
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])  # Title Only
    slide.shapes.title.text = "{{ company_name }}"
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def _xlsx_template() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws["A1"] = "{{ company_name }}"
    ws["A2"] = "{{ invoice_number }}"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# --- format discovery ------------------------------------------------------

def test_formats_endpoint(client):
    res = client.get("/api/formats")
    assert res.status_code == 200
    names = {f["name"] for f in res.get_json()["formats"]}
    assert {"txt", "md", "html", "csv", "docx", "pptx", "xlsx", "pdf"} <= names


# --- text-family formats ---------------------------------------------------

def test_generate_txt(client):
    res = client.post("/api/generate", data={
        "document_type": "txt",
        "content": json.dumps(CONTENT),
        "template_text": "Hello {{ customer_name }} ({{ invoice_number }})",
    })
    assert res.status_code == 200
    assert res.mimetype == "text/plain"
    assert b"Ada Lovelace" in res.data
    assert b"A-1042" in res.data


def test_generate_html(client):
    res = client.post("/api/generate", data={
        "document_type": "html",
        "content": json.dumps(CONTENT),
        "template_text": "<h1>{{ company_name }}</h1>",
    })
    assert res.status_code == 200
    assert res.mimetype == "text/html"
    assert b"Acme Corp" in res.data


def test_generate_pdf(client):
    res = client.post("/api/generate", data={
        "document_type": "pdf",
        "content": json.dumps(CONTENT),
        "template_text": "<h1>{{ company_name }}</h1><p>{{ invoice_number }}</p>",
    })
    assert res.status_code == 200
    assert res.mimetype == "application/pdf"
    assert res.data[:4] == b"%PDF"


# --- office formats --------------------------------------------------------

def test_generate_docx(client):
    res = client.post("/api/generate", data={
        "document_type": "docx",
        "content": json.dumps(CONTENT),
        "template": (io.BytesIO(_docx_template()), "t.docx"),
    }, content_type="multipart/form-data")
    assert res.status_code == 200
    assert res.data[:2] == b"PK"  # .docx is a zip container
    doc = Document(io.BytesIO(res.data))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "A-1042" in text
    assert "Ada Lovelace" in text


def test_generate_xlsx(client):
    res = client.post("/api/generate", data={
        "document_type": "xlsx",
        "content": json.dumps(CONTENT),
        "template": (io.BytesIO(_xlsx_template()), "t.xlsx"),
    }, content_type="multipart/form-data")
    assert res.status_code == 200
    ws = load_workbook(io.BytesIO(res.data)).active
    assert ws["A1"].value == "Acme Corp"
    assert ws["A2"].value == "A-1042"


def test_generate_pptx(client):
    res = client.post("/api/generate", data={
        "document_type": "pptx",
        "content": json.dumps(CONTENT),
        "template": (io.BytesIO(_pptx_template()), "t.pptx"),
    }, content_type="multipart/form-data")
    assert res.status_code == 200
    prs = Presentation(io.BytesIO(res.data))
    texts = [
        s.text_frame.text
        for slide in prs.slides
        for s in slide.shapes
        if s.has_text_frame
    ]
    assert any("Acme Corp" in t for t in texts)


# --- error handling --------------------------------------------------------

def test_unsupported_type(client):
    res = client.post("/api/generate", data={
        "document_type": "xyz", "content": "{}", "template_text": "x",
    })
    assert res.status_code == 400
    assert "Unsupported" in res.get_json()["error"]


def test_bad_json(client):
    res = client.post("/api/generate", data={
        "document_type": "txt", "content": "{not json", "template_text": "x",
    })
    assert res.status_code == 400
    assert "valid JSON" in res.get_json()["error"]


def test_missing_required_template(client):
    res = client.post("/api/generate", data={
        "document_type": "docx", "content": "{}",
    })
    assert res.status_code == 400
    assert "requires an uploaded template" in res.get_json()["error"]


def test_missing_content_key_is_error(client):
    # StrictUndefined: a placeholder with no matching key surfaces as an error.
    res = client.post("/api/generate", data={
        "document_type": "txt",
        "content": "{}",
        "template_text": "Hi {{ missing_key }}",
    })
    assert res.status_code == 500
    assert "Generation failed" in res.get_json()["error"]
