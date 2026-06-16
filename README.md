# Document Generator

A small Flask service that builds documents from **templates**. A calling app
supplies three things:

1. **Document type** — the output format to construct (`docx`, `pdf`, `pptx`, `xlsx`, `txt`, `md`, `html`, `csv`).
2. **Template** — an uploaded formatted template file (a real `.docx`/`.pptx`/`.xlsx`), or a pasted text/HTML template for the text-based formats.
3. **Content** — a JSON object whose keys fill the template's placeholders.

The same API powers a bundled web UI for testing by hand.

Templates use **Jinja2** syntax everywhere: `{{ variable }}` for values,
`{% for item in items %}…{% endfor %}` for loops, `{% if %}` for conditionals.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

(macOS/Linux: `source .venv/bin/activate`.)

Optionally generate the binary sample templates:

```powershell
python samples/make_samples.py
```

## Run

```powershell
python app.py
```

Open <http://localhost:5000>, choose a format, upload a template (or paste one),
edit the JSON content, and click **Generate & download**.

## API

| Method | Path | Purpose |
|--------|------|---------|
| `GET`  | `/`             | Test UI |
| `GET`  | `/api/formats`  | List supported output formats |
| `POST` | `/api/generate` | Generate a document |

### `POST /api/generate` (multipart/form-data)

| Field | Required | Description |
|-------|----------|-------------|
| `document_type` | yes | Output format (see table below). |
| `template`      | for `docx`/`pptx`/`xlsx` | Uploaded template file. |
| `template_text` | alt. | Pasted template string (allowed for `txt`/`md`/`html`/`csv`/`pdf`). |
| `content`       | yes | JSON object of fill values. |
| `filename`      | no  | Base name for the download (extension added automatically). |

**Success** → the generated file as a binary download (`Content-Disposition: attachment`).
**Failure** → JSON `{"error": "..."}` with a `400` (bad input) or `500` (render failure).

> Placeholders use `StrictUndefined` for the text-family and PDF formats: a
> placeholder with no matching content key returns an error rather than rendering
> blank. (docx/pptx/xlsx leave unmatched placeholders as-is.)

## Supported formats

| Type | Output | Library | Template |
|------|--------|---------|----------|
| `txt`  | Plain text | Jinja2 | text/upload |
| `md`   | Markdown   | Jinja2 | text/upload |
| `html` | HTML       | Jinja2 | text/upload |
| `csv`  | CSV        | Jinja2 | text/upload |
| `docx` | Word       | docxtpl | `.docx` upload |
| `pptx` | PowerPoint | python-pptx | `.pptx` upload |
| `xlsx` | Excel      | openpyxl | `.xlsx` upload |
| `pdf`  | PDF        | xhtml2pdf | HTML (text/upload) |

### PDF notes

PDF uses **xhtml2pdf** (pure Python, no system binaries) — give it an HTML
template. For higher fidelity or to mirror an Office template exactly:

- **WeasyPrint** — better HTML/CSS, but needs GTK installed on Windows.
- **Office → PDF** — fill a `.docx`/`.pptx` template then convert with
  LibreOffice headless (`soffice --headless --convert-to pdf`) or `docx2pdf`
  (needs MS Word). This is the route to a PDF that looks just like your template.

## Examples

PowerShell — fill a Word template:

```powershell
$form = @{
  document_type = 'docx'
  content       = '{"company_name":"Acme Corp","invoice_number":"A-1042","customer_name":"Ada Lovelace","date":"2026-06-15","items":[{"name":"Widget","amount":"$10.00"}],"total":"$10.00"}'
  template      = Get-Item .\samples\invoice.docx
}
Invoke-WebRequest -Uri http://localhost:5000/api/generate -Method Post -Form $form -OutFile out.docx
```

curl — render a pasted text template:

```bash
curl -X POST http://localhost:5000/api/generate \
  -F 'document_type=txt' \
  -F 'template_text=Hello {{ name }}!' \
  -F 'content={"name":"Ada"}' -o out.txt
```

## Project layout

```
app.py                 Flask app: routes + dispatch
generators/            one module per output format + the registry
templates/index.html   test UI
static/                UI JS + CSS
samples/               example templates (make_samples.py builds the binary ones)
tests/test_api.py      pytest end-to-end coverage
```

## Tests

```powershell
pytest
```

## Adding a new format

1. Create `generators/<name>_gen.py` exposing `generate(template_bytes, content) -> bytes`.
2. Add one `Format(...)` row to `REGISTRY` in `generators/__init__.py`.

The UI and `/api/formats` pick it up automatically.
