# Filter — Local PII / PHI anonymizer

Flask + React application using **Microsoft Presidio Analyzer** to identify private information before sharing text with an LLM. **Detection, parsing, language identification, NLP and OCR run locally; no LLM inference or external LLM APIs are used.** No API keys or Azure services are needed.

Found a bug or want to contribute? Read [CONTRIBUTING.md](CONTRIBUTING.md) for bug reports, development setup, testing, and pull request guidance. Use synthetic examples rather than real personal or medical documents.

## Quick start (Windows / PowerShell)

Prerequisites: Python 3.12 or 3.13 and Node.js 22+. Run these commands from the project directory:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-ner.txt
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run build
.venv/Scripts/python.exe -m app.main
```

Open **http://127.0.0.1:5000**. Flask serves the built React application and its same-origin API through Waitress. The server binds to loopback and runs without Flask debug mode. Keep the terminal running; Ctrl+C stops it.

After setup, Windows users can also double-click `start.bat` in the project folder. It changes to the correct directory automatically and keeps startup errors visible. In PowerShell the explicit relative command is `.\.venv\Scripts\python.exe -m app.main` (with `.\` at the beginning).

On Linux/macOS use `python3 -m venv .venv`, `.venv/bin/python`, and `npm` instead. Python 3.12/3.13 is recommended for the broadest availability of dependency wheels. Python 3.14 was also tested in this workspace.

### Updating an existing installation to Presidio

Stop the running server, then run:

```powershell
.venv/Scripts/python.exe -m pip install -r requirements-ner.txt
npm.cmd --prefix frontend run build
.venv/Scripts/python.exe -m app.main
```

Refresh the browser and anonymize your document again. The engine footer and `/api/health` should report `Microsoft Presidio (local)` and its installed version.

### How Presidio detection is configured

[Presidio Analyzer](https://presidio.dataprivacystack.org/analyzer/) runs in the Flask process. Its registry includes local NLP person/location recognition, email, phone and SSN recognizers, plus custom recognizers for document labels, DOBs, national IDs, addresses, postal codes and medical/lab identifiers. No cloud or remote recognizers are registered.

The engine uses a recognition-score threshold of `0.5`. Scores are recognizer heuristics; spaCy entity scores are defaults, not calibrated probabilities. Raising a threshold alone does not reliably distinguish a software reference from a place. A scoped technical-context recognizer uses skills-field labels, list structure and usage phrases; it does not look up product names. Explicit `Patient:`, `Dr.`, `Location:` and identifier patterns remain active. Ambiguous text still needs review.

Numeric candidates are validated before they become protected masking spans. `app/numeric_context.py` recognizes measurement/result/reference-range structure with dimensional unit syntax, without looking up analyte names or sample values. This prevents rows such as `139 136-145 mEq/L` from becoming phone numbers, and prevents five-digit measurement values from becoming postal codes. Both custom regex and built-in Presidio phone candidates pass the same validation. Unlabelled phone candidates must match complete regional digit-grouping metadata; explicit contact fields and international numbers receive possible-number validation. Seven-digit local numbers remain supported. Validation checks syntax, not whether a number is assigned or reachable. Explicit ID fields are not exempted by measurement context. Unitless numeric columns and ambiguous prose may still require manual review.

Only a preinstalled `SPACY_MODEL` is loaded. Runtime model downloads and email public-suffix-list fetches are bypassed. Presidio document/context logging is suppressed. A missing Presidio package/model produces an unavailable health state and HTTP 503 on anonymization; the app does not silently fall back to the previous detector. Install the dependencies and restart to recover.

The app keeps its existing overlap handling and consistent replacement tokens after detection returns entity spans. Presidio identifies sensitive spans with local recognizers and context validation. Replacement rendering remains local application code.

### Enable image and scanned-PDF OCR

Install the **Tesseract executable and language data**, separately from the Python wrapper. [Tesseract's installation guide](https://tesseract-ocr.github.io/tessdoc/Installation.html) links to the Windows installer and platform package instructions.

The app checks `.tools/tesseract/tesseract.exe` in this project, PATH, and standard Windows installation folders. `start.bat` explicitly uses the project-local executable when present. To install the Windows program, run:

```powershell
winget install --id UB-Mannheim.TesseractOCR --exact --source winget
```

Restart Flask after updating the Python source. Once this version is running, installing OCR is detected without restarting the terminal. An explicit `TESSERACT_CMD` takes priority over automatic detection.

This workspace also has a complete local runtime copied into `.tools/tesseract`, including its DLLs and language data. Keep that directory intact. It is ignored by Git, so another checkout needs its own Tesseract installation or local runtime copy.

```powershell
# If Tesseract is not on PATH, set this before starting Flask:
$env:TESSERACT_CMD = 'C:\Program Files\Tesseract-OCR\tesseract.exe'
$env:OCR_LANG = 'eng'
.venv/Scripts/python.exe -m app.main
```

On Debian/Ubuntu: `sudo apt-get install tesseract-ocr tesseract-ocr-eng fonts-dejavu-core`. On macOS: `brew install tesseract`.

Without Tesseract, TXT, DOCX and PDFs with text layers still work. Image/scanned-page requests return a clear setup error rather than silently returning empty text. The UI reports OCR availability. Add local Tesseract language packs and set `OCR_LANG`, e.g. `eng+fra`, to support other OCR languages.

### Docker (includes NER model and OCR)

```sh
docker build -t filter-local .
docker run --rm --name filter-local -p 127.0.0.1:5000:5000 --read-only --tmpfs /tmp:rw,noexec,nosuid,size=128m filter-local
```

The multi-stage image bundles the React build, spaCy model, Tesseract and English OCR data. It runs as a non-root user. The image needs network access **during the build** for dependencies; processing needs no outbound network. Docker configuration is provided but was not executed in this Windows workspace.

### Development

Run Flask as above, then in another terminal:

```powershell
npm.cmd --prefix frontend run dev
```

Open http://127.0.0.1:5173. Vite proxies `/api` to the local Flask server. No permissive CORS configuration is used. Build the frontend again to see frontend edits on port 5000.

## What it does

- Paste up to 100,000 characters with live word and character counts, or upload PDF, DOCX, UTF-8 TXT, PNG, JPEG, TIFF or WebP. WebP images use the same offline OCR and quality checks as other images.
- Extract text locally using pypdf / python-docx / Pillow / Tesseract; rasterize scanned PDF pages using PDFium.
- Reconstruct PDF lines from page positions so individually positioned words stay together. Normalize extraction padding before detection while keeping separate rows and paragraph gaps. Unsupported or incomplete layout extraction falls back to the complete plain text. Re-upload a document after updating the backend to refresh previously extracted text.
- Clean PDF, DOCX and OCR extraction padding, repeated horizontal spaces and excessive blank lines, while preserving paragraph, label, list and table-row boundaries. Pasted text and TXT uploads keep their original whitespace. The two editors share the same text typography and an aligned file-source row.
- Scale small images (up to 4×), flatten transparency onto white, and combine page and sparse-layout OCR passes by spatial region. Display low-resolution/uncertain-word warnings and mean word confidence. Processing stays offline and shares a 30-second OCR budget per page.
- Identify language with deterministic, seeded `langdetect`; show its code and probability estimate after processing.
- Detect names, locations, SSNs, context-labeled national IDs, Aadhaar-shaped numbers, PAN-shaped IDs, dates and DOBs, emails, phones, MRNs, lab accession/sample/barcode IDs, street addresses and postal codes.
- Use **Microsoft Presidio Analyzer** with a preinstalled offline spaCy model, built-in local recognizers and custom document/medical recognizers. Technical context reduces false person/location matches for software names. Priority-based overlap handling masks the entire connected span. Full repeated names/values receive consistent tokens within a request.
- Choose semantic tokens such as `[NAME_1]`, `[DATE_OF_BIRTH_1]`, `[SSN_MASKED_1]`, `[LAB_ID_1]`, `[REDACTED]`, or solid blocks.
- Review monochrome entity highlights, language, category counts and engine warnings. Entity types use labels and distinct border patterns rather than color. Choose detection categories.
- Use a black, white and neutral grayscale interface with a 12px minimum font size, including mobile layouts, tooltips, dialogs and badges. Editor text is 14px.
- Open directly into the paste/upload and side-by-side review workspace beside the Filter sidebar. Introductory headings and banners are omitted; navigation, help and privacy details remain available. The editors retain their existing responsive dimensions.
- Copy the anonymized text or export TXT / a fresh text-only PDF. Original files, PDF metadata, images and document structure are not copied to exports.
- Clear the session. Original content and results are held in React component memory; browser storage is not used.

Reversible mapping is deliberately omitted (it was optional). Tokens are consistent within one request, but no de-anonymization dictionary or original values are returned in the API response. Original text remains visible in the input review pane.

## Project structure

```text
app/
  main.py          Flask app factory, routes, headers, request limits
  patterns.py      Regex definitions and candidate spans
  presidio_engine.py Local Presidio initialization, health and detection adapter
  presidio_recognizers.py Offline NLP, built-in and custom document recognizers
  technical_context.py Scoped software-term disambiguation
  nlp.py           Explicit contextual name/location fields
  language.py      Local statistical language detection
  redactor.py      Overlap resolution and consistent substitutions
  extraction.py    PDF, DOCX, TXT and image/OCR parsing
  text_format.py   Conservative whitespace cleanup for extracted documents
  ocr.py           Image preprocessing, layout passes and quality diagnostics
  exports.py       Text-only PDF generation
  schemas.py       Public response type definitions
  errors.py        Safe user-facing errors, separate from parser exceptions
frontend/
  src/main.jsx     React UI, uploads, review, settings and exports
  src/styles.css   Responsive interface and layout
  src/theme.css    Monochrome palette and 12px-minimum typography
  src/workspace.css Compact workspace placement, preserving editor dimensions
  vite.config.js   Same-origin development API proxy
tests/
  test_pipeline.py API, detection, extraction, export and privacy regressions
requirements.txt       Python libraries, including Presidio Analyzer and spaCy
requirements-ner.txt   Libraries plus bundled English model
Dockerfile             Complete deployment including Tesseract
```

## API

| Method | Route | Request | Response |
| --- | --- | --- | --- |
| GET | `/api/health` | None | Local engine, NER/model and OCR availability |
| POST | `/api/extract` | Multipart `file` | `{ "text": "..." }` |
| POST | `/api/anonymize` | JSON `text`, optional `mode`, `enabled` | Masked text, entity offsets, counts, language and warnings |
| POST | `/api/export/pdf` | JSON `text` (the anonymized output) | PDF attachment |

Example:

```json
{"text":"Patient: Olivia Bennett\nDOB: 08/14/1986","mode":"tags","enabled":["NAME","DOB","EMAIL","SSN"]}
```

Modes: `tags`, `redact`, `blocks`. `enabled` defaults to all types; an empty list intentionally disables all detection. Entity `start`/`end` offsets are Python Unicode code-point offsets into the original input, with an exclusive end. The React viewer converts text to code points before slicing, including for emoji.

For image or scanned-PDF OCR, `/api/extract` additionally returns `warnings` and `ocr` metadata (word confidence estimate, page count, uncertain-word count and source dimensions). These warnings remain visible through anonymization. Low-resolution previews cannot reliably reproduce tiny, blurred or cropped characters; use the original PDF or a sharper scan when possible. More extracted text does not imply that names and identifiers were read correctly. The app does not use an LLM to guess missing text.

The PDF endpoint exports the supplied text; API callers must send the anonymized result. The UI does so. This endpoint is not an independent anonymizer.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `HOST` | `127.0.0.1` | Server interface (keep loopback for personal use) |
| `PORT` | `5000` | Server port |
| `SPACY_MODEL` | `en_core_web_sm` | Name or path of a preinstalled local model |
| `REQUIRE_NER` | unset | Set `1` to refuse startup if Presidio or its model is unavailable |
| `TESSERACT_CMD` | `tesseract` | Local executable path |
| `OCR_LANG` | `eng` | Preinstalled Tesseract language(s) |
| `PDF_FONT` | auto-detected | Local TTF with the characters needed for export |
| `TRUSTED_HOSTS` | `localhost,127.0.0.1,[::1]` | Comma-separated accepted Host headers |

The standard setup installs Presidio and the English model. Installing `requirements.txt` without a model does not provide working anonymization: health reports the missing detector and processing returns HTTP 503. Runtime code never downloads a missing model. [spaCy's model documentation](https://spacy.io/usage/models) explains local model installation. `REQUIRE_NER=1` also refuses server startup when the required detector cannot load.

## Privacy and security boundaries

- Original text is sent only to the app's Flask origin. Run it on your computer to keep content on your computer. A remote deployment receives originals on that server.
- No analytics, remote fonts, CDN scripts, external LLM SDKs, database, cookies, document history or browser persistence.
- APIs use POST bodies, `Cache-Control: no-store`, same-origin checks, trusted Host checks, restrictive CSP, frame denial and MIME-sniffing prevention. The frontend renders untrusted documents as React text nodes.
- Uploaded content is read into memory and not explicitly saved. The configured Waitress input-buffer threshold is above the entire allowed request size to avoid request-body disk spooling. Flask uses an in-memory upload stream. Tesseract creates temporary local image/text files and cleans them after OCR; use an encrypted local temporary volume or the Docker tmpfs for sensitive use.
- No document body logging; parser exception details are not returned or logged by this app. pypdf warnings are suppressed. OS swap, crash dumps, clipboard history, downloads, reverse proxies and host monitoring are outside this app's memory-retention guarantees.
- Limits: 10 MB files, 100,000 extracted/input characters, 20 PDF pages/image frames, 20 megapixels per image, 30-second OCR timeout per page, and DOCX archive member/expanded-size limits. PDF parser decompression can allocate memory before checks. For hostile documents or shared deployments, use a separate sandboxed worker with OS memory/CPU limits; these checks are not a complete parser sandbox.
- Text extraction may omit embedded DOCX images, text boxes, comments, tracked revisions or PDF image regions on otherwise text-bearing pages. OCR fallback runs on pages with no extracted text, not mixed-content regions. Review the extracted input before relying on results.
- The default model and contextual patterns primarily support **English**. Language detection alone does not provide multilingual NER. Identifiers are heuristic: formats are not globally exhaustive, false positives/negatives are expected, and postal/numeric formats can be ambiguous.
- Exports contain extracted text rather than the source layout. PDF Unicode coverage depends on the local font; use TXT for scripts without a supported font.
- This is a review aid, not a guarantee of de-identification or HIPAA/GDPR certification. Review output before sharing. Exposing it to other users requires authentication, TLS, rate limiting, resource isolation and a deployment-specific retention policy.

## Verification

```powershell
.venv/Scripts/python.exe -m pytest -q
npm.cmd --prefix frontend run build
```

Tests exercise the real Presidio engine, preservation of technical skills and clinical measurements, masking modes, category filtering, Unicode offsets, deterministic language detection, cold-start and detection with network/downloads blocked, missing-model behavior, log privacy, upload validation, TXT/DOCX/PDF extraction, PDF output, cross-origin rejection, security headers and parser error privacy. A separate integration check for actual OCR can be run after installing Tesseract. No real patient records are included in fixtures.
