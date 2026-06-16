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
  - [`GET /api/health`](#get-apihealth)
  - [`GET /api/formats`](#get-apiformats)
  - [`POST /api/generate`](#post-apigenerate)
  - [Errors & machine codes](#errors--machine-codes)
- [Versioning](#versioning)
- [Authentication & CORS](#authentication--cors)
- [Supported formats](#supported-formats)
- [Missing-key strictness](#missing-key-strictness)
- [Writing templates](#writing-templates)
  - [Repeating content](#repeating-content)
- [Worked examples (per format)](#worked-examples-per-format)
- [Bundled sample templates](#bundled-sample-templates)
- [PDF fidelity notes](#pdf-fidelity-notes)
- [Deployment](#deployment)
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
                   strict          true|false         (optional)
                   filename        "invoice"          (optional)
                        │
                        ▼
                 (optional X-API-Key check)  →  app.py looks up the format
                        │
                        ▼
                 generators/<fmt>.generate(template_bytes, content, strict) -> bytes
                        │
                        ▼
           200  binary file download (Content-Disposition: attachment)
           4xx/5xx  JSON {"error": "...", "code": "..."}
```

Each output format is one module under `generators/` implementing a tiny
contract — `generate(template_bytes: bytes, content: dict, strict: bool | None = None)
-> bytes` — and one row in the `REGISTRY` table in
[`generators/__init__.py`](generators/__init__.py).

It is a **generic** renderer with multiple consumers: it contains no
document-domain logic (no résumé/letter/invoice awareness) — just template +
content in, file out.

---

## Requirements

- **Python 3.10+** (the code uses `X | None` type syntax).
- The Python packages in [`requirements.txt`](requirements.txt):
  Flask, waitress (production WSGI server), docxtpl, python-pptx, openpyxl,
  xhtml2pdf, markdown, pytest.
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

**Development** (Flask's built-in server, for local use only):

```powershell
python app.py
```

The server starts on <http://localhost:5000>. Debug/reload is **off by default**;
set `DEBUG=1` to enable it. Open that URL for the test UI, or point your calling
app at `http://localhost:5000/api/generate`.

**Production** — do *not* use the dev server. Run under a real WSGI server; see
[Deployment](#deployment). To change the port or other settings, see
[Configuration](#configuration).

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

| Method | Path             | Purpose                          | Auth |
|--------|------------------|----------------------------------|------|
| `GET`  | `/`              | Test UI (HTML page)              | open |
| `GET`  | `/api/health`    | Liveness + API version           | open |
| `GET`  | `/api/formats`   | List supported output formats    | open |
| `POST` | `/api/generate`  | Generate and return a document   | `X-API-Key` if configured |

### `GET /api/health`

Liveness probe and version discovery. Always open (never requires auth), so it's
safe for load balancers and monitors.

```bash
curl http://localhost:5000/api/health
```

```json
{"status": "ok", "version": "1.0.0"}
```

### `GET /api/formats`

Returns the formats the server supports plus the API `version` — this is exactly
what the UI dropdown is built from, so a caller can discover capabilities
dynamically.

```bash
curl http://localhost:5000/api/formats
```

```json
{
  "version": "1.0.0",
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
| `strict`        | no                             | Override missing-key behavior: `true`/`false`. Omit to use the per-format default. See [Missing-key strictness](#missing-key-strictness). |
| `filename`      | no                             | Base name for the download; the correct extension is added if missing. Sanitized server-side (path separators, traversal and control chars are stripped). |

Header: send `X-API-Key: <key>` if the server is started with an `API_KEY`
(see [Authentication & CORS](#authentication--cors)).

**Success** → `200` with the generated file as a binary download
(`Content-Disposition: attachment; filename=...`) and the format's MIME type.

**Failure** → JSON `{"error": "...", "code": "..."}` with the appropriate HTTP
status. Check the status code (or `Content-Type`) to distinguish the binary
success from a JSON error.

### Errors & machine codes

**Every** error — including framework defaults like 413 and 404 — returns the
JSON envelope `{"error": "<message>", "code": "<machine_code>"}` with a stable
machine-readable `code`:

| Status | `code` | When | Example message |
|--------|--------|------|-----------------|
| `400` | `unsupported_type` | Unknown `document_type` | `Unsupported document_type 'xyz'. Supported: csv, docx, …` |
| `400` | `invalid_json` | `content` is not valid JSON | `content is not valid JSON: …` |
| `400` | `content_not_object` | `content` is JSON but not an object (list/number/…) | `content must be a JSON object (key/value pairs)` |
| `400` | `template_required` | Office format with no uploaded file | `'docx' requires an uploaded template file.` |
| `400` | `no_template` | No template at all (file or text) | `No template provided. Upload a file or supply 'template_text'.` |
| `401` | `unauthorized` | `API_KEY` configured and `X-API-Key` missing/wrong | `Missing or invalid API key.` |
| `413` | `too_large` | Request exceeds the 16 MB cap | `Request exceeds the 16 MB size limit.` |
| `500` | `render_failed` | Missing key (strict), bad template syntax, corrupt upload, PDF conversion error, … | `Generation failed: 'missing_key' is undefined` |

> The `code` field is the contract for branching in calling code — prefer it over
> string-matching the human-readable `error` message. Other framework errors
> (e.g. 404, 405) also return JSON, with a `code` derived from the HTTP status
> name (e.g. `not_found`).

---

## Versioning

The API exposes a semver `version` string (currently `1.0.0`) via both
`GET /api/health` and `GET /api/formats`. Consumers can read it at startup and
pin/branch on it. The version is defined as `API_VERSION` in
[`app.py`](app.py); bump it when the request/response contract changes. There is
no version in the URL path — the string is the contract marker.

---

## Authentication & CORS

Both are **opt-in via environment variables** and off by default, so
server-to-server use needs no configuration.

**API key.** Set `API_KEY` to require an `X-API-Key` header on
`POST /api/generate`:

```powershell
$env:API_KEY = "your-secret"      # PowerShell
```
```bash
export API_KEY=your-secret         # bash
```

When set, requests without a matching `X-API-Key` get `401 {"code":"unauthorized"}`.
`GET /api/health` and `GET /api/formats` stay open for discovery/monitoring.
When `API_KEY` is unset, `/api/generate` is open.

**CORS.** Set `ALLOWED_ORIGINS` (comma-separated) to allow browser clients from
those origins; use `*` to allow any:

```bash
export ALLOWED_ORIGINS="https://app.example.com,https://admin.example.com"
```

For an allowed `Origin`, responses include
`Access-Control-Allow-Origin`, `Vary: Origin`,
`Access-Control-Allow-Methods: GET, POST, OPTIONS` and
`Access-Control-Allow-Headers: Content-Type, X-API-Key`. With `ALLOWED_ORIGINS`
unset, no CORS headers are sent (strict default); server-to-server callers are
unaffected either way.

---

## Supported formats

| Type   | Output     | Engine              | Template source        | Default missing-key  |
|--------|------------|---------------------|------------------------|----------------------|
| `txt`  | Plain text | Jinja2              | paste or upload        | **error** (strict)   |
| `md`   | Markdown   | Jinja2              | paste or upload        | **error** (strict)   |
| `html` | HTML       | Jinja2              | paste or upload        | **error** (strict)   |
| `csv`  | CSV        | Jinja2              | paste or upload        | **error** (strict)   |
| `pdf`  | PDF        | Jinja2 → xhtml2pdf  | HTML (paste or upload) | **error** (strict)   |
| `docx` | Word       | docxtpl             | `.docx` upload         | renders **blank**    |
| `pptx` | PowerPoint | python-pptx + Jinja2| `.pptx` upload         | **error** (strict)   |
| `xlsx` | Excel      | openpyxl + Jinja2   | `.xlsx` upload         | **error** (strict)   |

The "Default missing-key" column is the behavior when the `strict` field is
omitted; you can override it per request — see below.

---

## Missing-key strictness

A placeholder whose key is absent from `content` is handled per the **`strict`**
form field. Omitting `strict` keeps each format's historical default (strict
everywhere except docx); sending it forces uniform behavior across all formats:

| `strict` value | Missing key behaves as | Applies to |
|----------------|------------------------|------------|
| *(omitted)* | strict for txt/md/html/csv/pdf/pptx/xlsx; **blank** for docx | per-format default |
| `true` | **error** (`render_failed` 500) | all formats |
| `false` | renders **empty** | all formats |

Accepted truthy/falsey strings: `true/1/yes/on` and `false/0/no/off`
(case-insensitive). Anything unrecognized is treated as "omitted".

> Use `strict=true` in development/CI to catch template/content mismatches early,
> and `strict=false` when partial content is expected and blanks are acceptable.
> Note: leniency makes *scalar* `{{ x }}` render empty, but iterating a missing
> list (`{% for i in items %}`) still errors — supply at least an empty list.

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

### Repeating content

**To repeat content (rows, line items, bullets), use a Jinja loop over a list
variable — never repeat the same placeholder.** Jinja renders one variable to
one value *everywhere it appears*, so duplicating `{{ item_name }}` down a column
just prints the same value in every cell. The correct pattern per format:

- **Text family / PDF / HTML** — loop in the template:
  ```jinja
  {% for item in items %}{{ item.name }}: {{ item.amount }}
  {% endfor %}
  ```
- **docx** — a `{% for %}` loop in the document; for clean table rows put
  `{%tr for item in items %}` / `{%tr endfor %}` on the row (docxtpl table tags).
- **pptx** — drive repeated bullets/paragraphs from a list and render
  per-paragraph; add paragraphs from one list variable rather than pasting many
  placeholders.
- **xlsx** — loop inside a single marker cell, or generate the repeated values
  from a list; don't paste the same `{{ x }}` into many cells.

Send the repeating data as a **JSON array** in `content`, e.g.
`{"items": [{"name": "Widget", "amount": "$10"}, …]}`. This keeps the service a
generic renderer — the *template* owns layout/repetition, the *content* owns data.

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

## Deployment

The Flask dev server (`python app.py`) is for local development only. In
production run the app under a real WSGI server — `waitress` (cross-platform,
included in `requirements.txt`) or `gunicorn` (Linux/macOS):

```powershell
# Windows
waitress-serve --listen=0.0.0.0:5000 app:app
```
```bash
# Linux / macOS
gunicorn -w 4 -b 0.0.0.0:5000 app:app
# ...or waitress works here too:
waitress-serve --listen=0.0.0.0:5000 app:app
```

`app:app` means "the `app` object in `app.py`". Set config via environment
variables before launching (see below). Generation is CPU-bound (especially PDF
and Office formats), so size your worker count and client timeouts accordingly;
each worker handles one request at a time.

Recommended production env:

```bash
export API_KEY=…                              # require X-API-Key
export ALLOWED_ORIGINS=https://app.example    # only if browsers call it directly
# DEBUG stays unset (off)
```

---

## Configuration

All configuration is via environment variables (read at startup):

| Variable | Default | Effect |
|----------|---------|--------|
| `API_KEY` | unset | If set, `POST /api/generate` requires header `X-API-Key: <value>` (else `401`). |
| `ALLOWED_ORIGINS` | unset | Comma-separated CORS allow-list (or `*`). Unset ⇒ no CORS headers. |
| `PORT` | `5000` | Port for the dev server (`python app.py`). WSGI servers take their own `--listen`/`-b`. |
| `DEBUG` | off | `1`/`true` enables Flask debug/reload on the dev server. Leave off in production. |

Other limits live in [`app.py`](app.py):

- **Upload size cap** — `MAX_CONTENT_LENGTH = 16 * 1024 * 1024` (16 MB).
  Larger requests get `413 {"code":"too_large"}`.
- **API version** — `API_VERSION` (semver), surfaced via `/api/health` and
  `/api/formats`.

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
  _jinja.py            shared Jinja2 env builder + strictness resolver
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
   `generate(template_bytes: bytes, content: dict, strict: bool | None = None) -> bytes`.
   For Jinja-based formats, build the env with `make_env(resolve_strict(strict,
   <default>))` from [`generators/_jinja.py`](generators/_jinja.py).
2. Add one `Format(...)` row to `REGISTRY` in
   [`generators/__init__.py`](generators/__init__.py) (set
   `requires_template=True` if it needs a binary upload).

The UI dropdown and `GET /api/formats` pick it up automatically — no other
changes needed. Keep generators generic: no document-type-specific logic.

---

## Troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| `render_failed`: `'<key>' is undefined` | Your template references a key not in `content`. Add the key, remove the placeholder, or send `strict=false` to render it blank. (docx is lenient by default.) |
| `template_required` (`'docx' requires an uploaded template file.`) | Office formats can't use `template_text` — attach a real `.docx`/`.pptx`/`.xlsx` via the `template` field. |
| `invalid_json` / `content_not_object` | The `content` field must be a JSON **object**, e.g. `{"name":"Ada"}` — not malformed JSON, a bare string, or a list. |
| The same value repeats in every row/cell | You duplicated a placeholder. Use a Jinja loop over a list variable instead — see [Repeating content](#repeating-content). |
| docx/pptx placeholder renders only partially or loses formatting | The placeholder was split across multiple formatting runs. Retype it in one go so it stays in a single run. |
| xlsx cell didn't get filled | The cell must contain a Jinja2 marker (`{{` or `{%`) and be a string cell; numeric/formula cells are skipped by design. |
| PDF looks plain or CSS is ignored | xhtml2pdf supports a CSS subset — simplify the CSS, or use WeasyPrint / the Office→PDF route above. |
| `401 unauthorized` | `API_KEY` is set on the server — send header `X-API-Key: <key>`. |
| CORS error in the browser | Set `ALLOWED_ORIGINS` to include your site's origin (see [Authentication & CORS](#authentication--cors)). |
| `413 too_large` | The request exceeded the 16 MB cap; raise `MAX_CONTENT_LENGTH` in `app.py`. |
