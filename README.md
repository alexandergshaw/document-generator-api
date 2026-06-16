# Document Generator

A small Flask service that builds documents from **templates**. A calling app
(or the bundled test UI) sends three things and gets a finished file back:

1. **Document type** — the output format to construct
   (`docx`, `pdf`, `pptx`, `xlsx`, `txt`, `md`, `html`, `csv`).
2. **Template** — an uploaded formatted file (a real `.docx` / `.pptx` / `.xlsx`),
   **or** a pasted text/HTML template for the text-based formats.
3. **Content** — a JSON object whose keys fill the template's placeholders.

The matching generator fills the template and streams the rendered document
back as a download. The same API powers a web UI for testing by hand.

Templates use **Jinja2** syntax everywhere: `{{ variable }}` for values,
`{% for item in items %}…{% endfor %}` for loops, `{% if cond %}…{% endif %}`
for conditionals.

---

## Table of contents

- [How it works](#how-it-works)
- [Requirements](#requirements)
- [Setup](#setup)
- [Run the server](#run-the-server)
- [Using the web UI](#using-the-web-ui)
- [Using the API](#using-the-api)
  - [`GET /api/formats`](#get-apiformats)
  - [`POST /api/generate`](#post-apigenerate)
  - [Errors](#errors)
- [Supported formats](#supported-formats)
- [Writing templates](#writing-templates)
- [Worked examples (per format)](#worked-examples-per-format)
- [Bundled sample templates](#bundled-sample-templates)
- [PDF fidelity notes](#pdf-fidelity-notes)
- [Configuration](#configuration)
- [Tests](#tests)
- [Project layout](#project-layout)
- [Adding a new format](#adding-a-new-format)
- [Troubleshooting](#troubleshooting)

---

## How it works

```
caller / UI ──▶  POST /api/generate (multipart/form-data)
                   document_type   "docx"
                   template        <uploaded .docx>   (or template_text="…")
                   content         {"customer_name": "Ada", …}
                   filename        "invoice"          (optional)
                        │
                        ▼
                 app.py looks up the format in the registry
                        │
                        ▼
                 generators/<fmt>.generate(template_bytes, content) -> bytes
                        │
                        ▼
           200  binary file download (Content-Disposition: attachment)
           4xx/5xx  JSON {"error": "..."}
```

Each output format is one module under `generators/` implementing a tiny
contract — `generate(template_bytes: bytes, content: dict) -> bytes` — and one
row in the `REGISTRY` table in [`generators/__init__.py`](generators/__init__.py).

---

## Requirements

- **Python 3.10+** (the code uses `X | None` type syntax).
- The Python packages in [`requirements.txt`](requirements.txt):
  Flask, docxtpl, python-pptx, openpyxl, xhtml2pdf, markdown, pytest.
- No system binaries required — PDF generation uses pure-Python `xhtml2pdf`,
  so a single `pip install` works on Windows, macOS and Linux.

---

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

(Optional) build the binary sample templates (`invoice.docx`, `deck.pptx`,
`sheet.xlsx`) so you have real Office files to upload while testing:

```powershell
python samples/make_samples.py
```

---

## Run the server

```powershell
python app.py
```

The server starts on <http://localhost:5000> with Flask debug/reload enabled.
Open that URL for the test UI, or point your calling app at
`http://localhost:5000/api/generate`.

To change the port or disable debug, see [Configuration](#configuration).

---

## Using the web UI

Open <http://localhost:5000>. The page is a thin client over the API
([`static/app.js`](static/app.js)) and walks through the same three inputs:

1. **Document type** — dropdown populated live from `GET /api/formats`.
   Selecting a type shows its description underneath.
2. **Template** — either:
   - **Upload a file** (required for `docx` / `pptx` / `xlsx`), or
   - **Paste a template** into the text box (allowed for `txt` / `md` / `html`
     / `csv` / `pdf`). If you upload a file, the pasted text is ignored.
3. **Content (JSON)** — a JSON object of fill values. Keys map to
   `{{ placeholders }}`; arrays drive `{% for %}` loops.
4. **Download filename** *(optional)* — base name for the saved file; the
   correct extension is appended automatically.

Click **Generate & download**. On success the browser downloads the file and
the status line shows the saved name; on failure the API's error message is
shown inline.

---

## Using the API

| Method | Path             | Purpose                          |
|--------|------------------|----------------------------------|
| `GET`  | `/`              | Test UI (HTML page)              |
| `GET`  | `/api/formats`   | List supported output formats    |
| `POST` | `/api/generate`  | Generate and return a document   |

### `GET /api/formats`

Returns the formats the server supports — this is exactly what the UI dropdown
is built from, so a caller can discover capabilities dynamically.

```bash
curl http://localhost:5000/api/formats
```

```json
{
  "formats": [
    {"name": "txt",  "extension": "txt",  "requires_template": false, "description": "Plain text rendered with Jinja2"},
    {"name": "md",   "extension": "md",   "requires_template": false, "description": "Markdown rendered with Jinja2"},
    {"name": "html", "extension": "html", "requires_template": false, "description": "HTML rendered with Jinja2"},
    {"name": "csv",  "extension": "csv",  "requires_template": false, "description": "CSV rendered with Jinja2"},
    {"name": "docx", "extension": "docx", "requires_template": true,  "description": "Word document from a .docx template (docxtpl)"},
    {"name": "pptx", "extension": "pptx", "requires_template": true,  "description": "PowerPoint from a .pptx template (python-pptx)"},
    {"name": "xlsx", "extension": "xlsx", "requires_template": true,  "description": "Excel workbook from a .xlsx template (openpyxl)"},
    {"name": "pdf",  "extension": "pdf",  "requires_template": false, "description": "PDF from an HTML template (xhtml2pdf)"}
  ]
}
```

`requires_template: true` means the template **must** be an uploaded binary file
(the Office formats). `false` means you may paste `template_text` instead.

### `POST /api/generate`

Send as **`multipart/form-data`** (so the template file can be attached).

| Field           | Required                       | Description                                                                 |
|-----------------|--------------------------------|-----------------------------------------------------------------------------|
| `document_type` | yes                            | Output format — one of the names from `/api/formats` (case-insensitive).     |
| `template`      | for `docx` / `pptx` / `xlsx`   | Uploaded template file. Takes priority over `template_text` if both are sent.|
| `template_text` | alternative to `template`      | Pasted template string. Allowed for `txt` / `md` / `html` / `csv` / `pdf`.   |
| `content`       | recommended (defaults to `{}`) | JSON **object** of fill values. Must be valid JSON and a key/value object.    |
| `filename`      | no                             | Base name for the download; the correct extension is added if missing.       |

**Success** → `200` with the generated file as a binary download
(`Content-Disposition: attachment; filename=...`) and the format's MIME type.

**Failure** → JSON `{"error": "..."}` with status `400` (bad input) or
`500` (template rendering failed).

### Errors

| Status | When | Example message |
|--------|------|-----------------|
| `400` | Unknown `document_type` | `Unsupported document_type 'xyz'. Supported: csv, docx, …` |
| `400` | `content` is not valid JSON | `content is not valid JSON: …` |
| `400` | `content` is JSON but not an object (e.g. a list/number) | `content must be a JSON object (key/value pairs)` |
| `400` | Office format with no uploaded file | `'docx' requires an uploaded template file.` |
| `400` | No template at all (file or text) | `No template provided. Upload a file or supply 'template_text'.` |
| `500` | Template references a missing key, bad template syntax, corrupt upload, etc. | `Generation failed: 'missing_key' is undefined` |
| `413` | Upload exceeds the 16 MB cap | (Flask `Request Entity Too Large`) |

---

## Supported formats

| Type   | Output     | Engine              | Template source        | Missing-key behavior        |
|--------|------------|---------------------|------------------------|-----------------------------|
| `txt`  | Plain text | Jinja2              | paste or upload        | **error** (`StrictUndefined`) |
| `md`   | Markdown   | Jinja2              | paste or upload        | **error** (`StrictUndefined`) |
| `html` | HTML       | Jinja2              | paste or upload        | **error** (`StrictUndefined`) |
| `csv`  | CSV        | Jinja2              | paste or upload        | **error** (`StrictUndefined`) |
| `pdf`  | PDF        | Jinja2 → xhtml2pdf  | HTML (paste or upload) | **error** (`StrictUndefined`) |
| `docx` | Word       | docxtpl             | `.docx` upload         | renders **blank**           |
| `pptx` | PowerPoint | python-pptx + Jinja2| `.pptx` upload         | **error** (`StrictUndefined`) |
| `xlsx` | Excel      | openpyxl + Jinja2   | `.xlsx` upload         | **error** (`StrictUndefined`) |

> **Missing-key behavior matters.** Most formats use Jinja2's `StrictUndefined`:
> a placeholder whose key is absent from `content` returns a `500` error rather
> than silently rendering blank — this catches typos early. The exception is
> **docx** (docxtpl uses Jinja2 defaults), where a missing key renders as an
> empty string.

---

## Writing templates

All formats share the same Jinja2 vocabulary:

| Syntax | Purpose |
|--------|---------|
| `{{ name }}` | insert a value |
| `{{ item.amount }}` / `{{ user['email'] }}` | nested access |
| `{% for row in rows %}…{% endfor %}` | loops (use `{{ loop.last }}`, `{{ loop.index }}`, …) |
| `{% if total %}…{% else %}…{% endif %}` | conditionals |
| `{{ price \| round(2) }}` | Jinja2 filters |

The `content` JSON you send becomes the template's variables: top-level keys are
the variable names, and nested objects/arrays are reachable with `.`/`[]` and
drive loops.

**Per-format notes:**

- **Text family (`txt`/`md`/`html`/`csv`)** — the whole template is one Jinja2
  string. **Autoescaping is off**, so HTML output is *not* escaped; only feed it
  content you trust (this is a generic templating tool where the caller controls
  both template and content).
- **`pdf`** — give it an **HTML** template; it's rendered with Jinja2 then
  converted to PDF. See [PDF fidelity notes](#pdf-fidelity-notes).
- **`docx`** — type Jinja2 placeholders directly into a Word document
  (docxtpl). Supports loops, conditionals and even image insertion. Keep a
  placeholder within a single run/format for predictable output.
- **`xlsx`** — only **string cells containing a marker** (`{{` or `{%`) are
  rendered; every other cell, plus formatting and formulas, is left untouched.
- **`pptx`** — placeholders in shape text frames and table cells are rendered
  per paragraph. *Limitation:* if a marker spans multiple runs with different
  formatting, the rendered text takes the first run's formatting and the other
  runs are emptied — keep each placeholder inside one run.

---

## Worked examples (per format)

Start the server first (`python app.py`). The examples below all reuse this
content object, which covers every placeholder in the bundled samples:

```json
{
  "company_name": "Acme Corp",
  "invoice_number": "A-1042",
  "customer_name": "Ada Lovelace",
  "date": "2026-06-15",
  "items": [
    {"name": "Widget", "amount": "$10.00"},
    {"name": "Gadget", "amount": "$25.00"}
  ],
  "total": "$35.00"
}
```

### Pasted text template (`txt` / `md` / `html` / `csv` / `pdf`)

**curl:**

```bash
curl -X POST http://localhost:5000/api/generate \
  -F 'document_type=txt' \
  -F 'template_text=Hello {{ customer_name }}, invoice {{ invoice_number }} total {{ total }}.' \
  -F 'content={"customer_name":"Ada Lovelace","invoice_number":"A-1042","total":"$35.00"}' \
  -o out.txt
```

**PowerShell:**

```powershell
$form = @{
  document_type = 'txt'
  template_text = 'Hello {{ customer_name }}, invoice {{ invoice_number }} total {{ total }}.'
  content       = '{"customer_name":"Ada Lovelace","invoice_number":"A-1042","total":"$35.00"}'
}
Invoke-WebRequest http://localhost:5000/api/generate -Method Post -Form $form -OutFile out.txt
```

For **`html`** or **`pdf`**, paste an HTML template instead — e.g. use
[`samples/report.html`](samples/report.html) as `template_text` and set
`document_type=pdf` to get a styled PDF.

### Office templates (`docx` / `pptx` / `xlsx`)

These require an uploaded file. Build the samples first
(`python samples/make_samples.py`), then:

**PowerShell — fill the Word invoice:**

```powershell
$form = @{
  document_type = 'docx'
  content       = '{"company_name":"Acme Corp","invoice_number":"A-1042","customer_name":"Ada Lovelace","date":"2026-06-15","items":[{"name":"Widget","amount":"$10.00"},{"name":"Gadget","amount":"$25.00"}],"total":"$35.00"}'
  template      = Get-Item .\samples\invoice.docx
  filename      = 'acme-invoice'
}
Invoke-WebRequest http://localhost:5000/api/generate -Method Post -Form $form -OutFile acme-invoice.docx
```

**curl — fill the Excel sheet:**

```bash
curl -X POST http://localhost:5000/api/generate \
  -F 'document_type=xlsx' \
  -F 'template=@samples/sheet.xlsx' \
  -F 'content={"company_name":"Acme Corp","invoice_number":"A-1042","customer_name":"Ada Lovelace","date":"2026-06-15","total":"$35.00"}' \
  -o invoice.xlsx
```

Swap `document_type` to `pptx` and `template=@samples/deck.pptx` for slides.

### Python client (`requests`)

```python
import requests

content = {
    "company_name": "Acme Corp",
    "invoice_number": "A-1042",
    "customer_name": "Ada Lovelace",
    "date": "2026-06-15",
    "items": [{"name": "Widget", "amount": "$10.00"}],
    "total": "$10.00",
}

with open("samples/invoice.docx", "rb") as tpl:
    resp = requests.post(
        "http://localhost:5000/api/generate",
        data={"document_type": "docx", "content": __import__("json").dumps(content),
              "filename": "acme-invoice"},
        files={"template": ("invoice.docx", tpl)},
    )

resp.raise_for_status()
with open("acme-invoice.docx", "wb") as out:
    out.write(resp.content)
```

For a text format, drop `files=` and pass `template_text` inside `data`.

---

## Bundled sample templates

In [`samples/`](samples/):

| File | Format | Notes |
|------|--------|-------|
| `letter.txt`  | `txt` | Plain-text letter with a `{% for %}` items loop. Checked in. |
| `report.html` | `html` / `pdf` | Styled HTML invoice with a table. Checked in. |
| `invoice.docx`| `docx` | Generated by `make_samples.py`. |
| `deck.pptx`   | `pptx` | Generated by `make_samples.py`. |
| `sheet.xlsx`  | `xlsx` | Generated by `make_samples.py`. |

The three Office files are **not** committed (they're build artifacts) — run
`python samples/make_samples.py` to create them.

---

## PDF fidelity notes

PDF uses **xhtml2pdf** (pure Python, no system binaries) and takes an HTML
template. It handles common HTML/CSS but isn't a full browser engine. For
higher fidelity:

- **WeasyPrint** — much better HTML/CSS support, but needs GTK installed on
  Windows.
- **Office → PDF** — fill a `.docx`/`.pptx` template with this API, then convert
  the result with LibreOffice headless
  (`soffice --headless --convert-to pdf out.docx`) or `docx2pdf` (needs MS
  Word). This is the route to a PDF that looks exactly like your Office template.

---

## Configuration

Settings live at the top of [`app.py`](app.py):

- **Port / debug** — `app.run(debug=True, port=5000)`. Change the port or set
  `debug=False` for a non-reloading run. For production, serve with a WSGI
  server instead, e.g. `waitress-serve --port=5000 app:app`.
- **Upload size cap** — `MAX_CONTENT_LENGTH = 16 * 1024 * 1024` (16 MB).
  Requests larger than this get a `413`.

---

## Tests

End-to-end tests cover every format and the main error paths. They build
templates in memory, so they don't depend on `samples/` being generated.

```powershell
pytest
```

---

## Project layout

```
app.py                 Flask app: routes + request dispatch
generators/
  __init__.py          Format dataclass + REGISTRY + lookup helpers
  text.py              txt / md / html / csv (Jinja2)
  docx_gen.py          docx (docxtpl)
  pptx_gen.py          pptx (python-pptx + Jinja2)
  xlsx_gen.py          xlsx (openpyxl + Jinja2)
  pdf_gen.py           pdf (Jinja2 HTML -> xhtml2pdf)
templates/index.html   test UI
static/app.js          UI logic (calls the API)
static/style.css       UI styles
samples/               example templates (make_samples.py builds the binary ones)
tests/test_api.py      pytest end-to-end coverage
requirements.txt       Python dependencies
```

---

## Adding a new format

1. Create `generators/<name>_gen.py` exposing
   `generate(template_bytes: bytes, content: dict) -> bytes`.
2. Add one `Format(...)` row to `REGISTRY` in
   [`generators/__init__.py`](generators/__init__.py) (set
   `requires_template=True` if it needs a binary upload).

The UI dropdown and `GET /api/formats` pick it up automatically — no other
changes needed.

---

## Troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| `Generation failed: '<key>' is undefined` | Your template references a key not present in `content`. Add the key, or remove the placeholder. (docx renders these blank instead of erroring.) |
| `'docx' requires an uploaded template file.` | Office formats can't use `template_text` — attach a real `.docx`/`.pptx`/`.xlsx` via the `template` field. |
| `content is not valid JSON` | The `content` field must be a JSON **object**, e.g. `{"name":"Ada"}` — not a bare string or list. |
| docx/pptx placeholder renders only partially or loses formatting | The placeholder was split across multiple formatting runs. Retype it in one go so it stays in a single run. |
| xlsx cell didn't get filled | The cell must contain a Jinja2 marker (`{{` or `{%`) and be a string cell; numeric/formula cells are skipped by design. |
| PDF looks plain or CSS is ignored | xhtml2pdf supports a CSS subset — simplify the CSS, or use WeasyPrint / the Office→PDF route above. |
| `413 Request Entity Too Large` | The upload exceeded the 16 MB cap; raise `MAX_CONTENT_LENGTH` in `app.py`. |
