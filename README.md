# Veil — Local PII / PHI anonymizer

Flask + React application for reviewing and masking sensitive information before sharing text with an LLM. **Detection, parsing, language identification, NLP and OCR run locally; no external LLM APIs are used.** No API keys are needed.

## Quick start (Windows / PowerShell)

Prerequisites: Python 3.12+ and Node.js 22+. Run these commands from the project directory:

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
docker build -t veil-local .
docker run --rm --name veil-local -p 127.0.0.1:5000:5000 --read-only --tmpfs /tmp:rw,noexec,nosuid,size=128m veil-local
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
- Scale small images (up to 4×), flatten transparency onto white, and combine page and sparse-layout OCR passes by spatial region. Display low-resolution/uncertain-word warnings and mean word confidence. Processing stays offline and shares a 30-second OCR budget per page.
- Identify language with deterministic, seeded `langdetect`; show its code and probability estimate after processing.
- Detect names, locations, SSNs, context-labeled national IDs, Aadhaar-shaped numbers, PAN-shaped IDs, dates and DOBs, emails, phones, MRNs, lab accession/sample/barcode IDs, street addresses and postal codes.
- Combine regex and contextual patterns with an **installed offline spaCy model**. Priority-based overlap handling masks the entire connected span. Full repeated names/values receive consistent tokens within a request.
- Choose semantic tokens such as `[PATIENT_NAME_1]`, `[DATE_OF_BIRTH_1]`, `[SSN_MASKED_1]`, `[LAB_ID_1]`, `[REDACTED]`, or solid blocks.
- Review color-coded entities, language, category counts and engine warnings. Choose detection categories.
- Copy the anonymized text or export TXT / a fresh text-only PDF. Original files, PDF metadata, images and document structure are not copied to exports.
- Clear the session. Original content and results are held in React component memory; browser storage is not used.

Reversible mapping is deliberately omitted (it was optional). Tokens are consistent within one request, but no de-anonymization dictionary or original values are returned in the API response. Original text remains visible in the input review pane.

## Project structure

```text
app/
  main.py          Flask app factory, routes, headers, request limits
  patterns.py      Regex definitions and candidate spans
  nlp.py           Local spaCy NER and contextual name/location rules
  language.py      Local statistical language detection
  redactor.py      Overlap resolution and consistent substitutions
  extraction.py    PDF, DOCX, TXT and image/OCR parsing
  ocr.py           Image preprocessing, layout passes and quality diagnostics
  exports.py       Text-only PDF generation
  schemas.py       Public response type definitions
  errors.py        Safe user-facing errors, separate from parser exceptions
frontend/
  src/main.jsx     React UI, uploads, review, settings and exports
  src/styles.css   Responsive interface and entity colors
  vite.config.js   Same-origin development API proxy
tests/
  test_pipeline.py API, detection, extraction, export and privacy regressions
requirements.txt       Python libraries, including spaCy
requirements-ner.txt   Libraries plus bundled English model
Dockerfile             Complete deployment including Tesseract
```

## API

| Method | Route | Request | Response |
| --- | --- | --- | --- |
| GET | `/api/health` | None | Local engine, NER/model and OCR availability |
| POST | `/api/extract` | Multipart `file` | `{ "text": "..." }` |
| POST | `/api/anonymize` | JSON `text`, optional `mode`, optional `enabled` | Masked text, non-overlapping entity offsets, counts, language, warnings |
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
| `REQUIRE_NER` | unset | Set `1` to refuse startup if the model is unavailable |
| `TESSERACT_CMD` | `tesseract` | Local executable path |
| `OCR_LANG` | `eng` | Preinstalled Tesseract language(s) |
| `PDF_FONT` | auto-detected | Local TTF with the characters needed for export |
| `TRUSTED_HOSTS` | `localhost,127.0.0.1,[::1]` | Comma-separated accepted Host headers |

The standard setup installs the model. To run only contextual rules, install `requirements.txt` without the model: the UI prominently warns of limited name/location coverage. Runtime code never downloads a missing model. [spaCy's model documentation](https://spacy.io/usage/models) explains local model installation. Enable `REQUIRE_NER=1` for deployments that must always have statistical NER.

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

Tests exercise removal and consistency, preservation of clinical measurements, masking modes, category filtering, Unicode offsets, deterministic language detection, network-denied detection, upload validation, TXT/DOCX/PDF extraction, PDF output, cross-origin rejection, security headers and parser error privacy. A separate integration check for actual OCR can be run after installing Tesseract. No real patient records are included in fixtures.
