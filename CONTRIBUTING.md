# Contributing to Filter

You can help by reporting bugs, improving detection, fixing document extraction,
testing OCR, improving accessibility, or clarifying documentation. Small, focused
contributions are welcome.

Filter uses Flask and React, Microsoft Presidio with an offline spaCy model, and
Tesseract OCR. Document processing must stay on the application server: do not add
external LLM APIs, remote OCR services, or document-content telemetry.

## Report a bug

Search the repository's **Issues** tab for an existing report first. If there is
no matching issue, open a new one with a short, descriptive title and the details
below. You do not need to submit code to report a bug.

```text
Summary:

Steps to reproduce:
1.
2.
3.

Expected behavior:

Actual behavior and exact error:

Environment:
- Operating system and browser:
- Python and Node.js versions, if running locally:
- Local, Docker, or hosted deployment:
- Commit or branch, if known:
- Document format, page count, size, and language:
- Presidio/spaCy and Tesseract versions, if relevant:

Minimal synthetic example:

Screenshots or sanitized logs, if helpful:
```

- Use invented names, identifiers, contact information, and documents. Never
  attach patient records, customer documents, credentials, private keys, deploy
  hooks, or other real PII/PHI to an issue, pull request, screenshot, or fixture.
- For detection bugs, show the synthetic input, actual replacement, and expected
  replacement. State whether the problem is a false positive (ordinary text
  masked) or a false negative (sensitive text left visible).
- For OCR bugs, include a small synthetic image/document that preserves the
  problematic layout, font size, and resolution. Check the entire attachment for
  sensitive metadata as well as visible text.
- For performance bugs, include file dimensions/page count, approximate request
  duration, hosting resources, and whether the first request after inactivity is
  the only slow one. Share timing metadata rather than document contents.

## Report a security or privacy problem

Use a maintainer-provided private reporting channel. If GitHub private vulnerability
reporting is enabled, use **Security → Report a vulnerability**. If no private
channel is available, open an issue requesting one without publishing the
vulnerability details, sensitive documents, or exploit payloads.

## Propose a feature

Open an issue describing the user problem, a concrete example, and the expected
behavior before starting a large change. Explain any effect on privacy,
dependencies, OCR accuracy, supported languages, memory use, or deployment costs.

## Set up a development environment

1. Fork the repository, clone your fork, and create a branch for your change:

   ```sh
   git clone YOUR_FORK_URL Filter
   cd Filter
   git switch -c fix/describe-the-problem
   ```

2. Install Python 3.12 or 3.13 and Node.js 22 or later. From the repository root,
   set up the dependencies on Windows/PowerShell:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements-ner.txt
   npm.cmd --prefix frontend ci
   npm.cmd --prefix frontend run build
   ```

   On Linux/macOS, use `python3 -m venv .venv`, `.venv/bin/python` and `npm`
   instead of the Windows executable paths and `npm.cmd`.

3. Install the Tesseract executable and the required language data to work on
   image/scanned-PDF extraction. The Python package alone does not install the
   OCR executable. See the [README](README.md) for platform-specific setup and
   `TESSERACT_CMD`/`OCR_LANG` configuration. The ignored `.tools` directory is not
   included when you clone the repository.

4. Start the backend:

   ```powershell
   .\.venv\Scripts\python.exe -m app.main
   ```

5. In a second terminal, start the frontend:

   ```powershell
   npm.cmd --prefix frontend run dev
   ```

   Open the Local URL printed by Vite, normally `http://127.0.0.1:5173`.
   Vite forwards `/api` requests to Flask on port 5000. Restart Flask after Python
   edits; the current backend does not automatically reload. To view frontend
   edits on port 5000, rebuild the frontend.

Dependency/model downloads happen during setup. Processing documents must not
download models or make outbound requests. Verify `/api/health` reports Presidio
available and, when testing OCR, OCR available.

## Find the relevant code

| Area | Main files |
| --- | --- |
| API, validation, headers, and upload limits | `app/main.py` |
| Presidio and local recognizers | `app/presidio_engine.py`, `app/presidio_recognizers.py` |
| Rules and context validation | `app/patterns.py`, `app/nlp.py`, `app/numeric_context.py`, `app/technical_context.py` |
| Span overlap resolution and replacement tokens | `app/redactor.py` |
| Document parsing, PDF layout, and OCR | `app/extraction.py`, `app/pdf_text.py`, `app/ocr.py`, `app/text_format.py` |
| Language detection and PDF exports | `app/language.py`, `app/exports.py` |
| UI, upload state, highlighting, and copy/download | `frontend/src/main.jsx` |
| Styling | `frontend/src/*.css` |
| Regression coverage | `tests/` |

## Keep changes focused and privacy-preserving

- Preserve Microsoft Presidio, offline model loading, OCR support, and safe
  failure when a required detector is unavailable.
- Keep original document text out of logs. Do not add document history, browser
  persistence, or permanent uploads as a side effect of another change.
- Do not remove origin checks, trusted-host validation, file/resource limits, or
  security headers to work around a deployment problem.
- Fix detection problems through general structure and context validation, not
  dictionaries of names or sample values that happen to appear in one report.
  Check both false positives and false negatives across different contexts.
- Preserve offsets into the original text, consistent replacement tokens, and
  Unicode handling. A masking fix must not expose part of a sensitive span.
- For extraction changes, check that text is not silently lost and table rows or
  paragraphs are not accidentally joined. Compare OCR coverage as well as speed.
- Keep the UI black, white, and neutral grayscale, with text at least 12px. Keep
  existing editor dimensions unless the proposed change explicitly addresses
  layout. Maintain keyboard operation and accessible labels.
- Keep generated builds, dependency directories, OCR executables, credentials,
  and real user documents out of commits. Review `git diff` before submitting.

## Validate your change

For application-code changes, run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
npm.cmd --prefix frontend run build
git diff --check
```

Add a focused regression test for a bug fix when it can meaningfully demonstrate
the problem. Use synthetic fixtures. The suite includes real Presidio checks and
OCR integration checks; executable-dependent OCR tests may be skipped if
Tesseract is absent. State any skipped checks and why. OCR changes need validation
with a working Tesseract installation.

Manually check affected UI flows and report the result. For documentation-only
changes, verify commands and relative links and run `git diff --check`; a full
application test run is not necessary.

## Submit a pull request

Push your branch to your fork and open a pull request against this repository's
default branch. Link the related issue, if there is one. Include:

- The problem and the resulting behavior after the change.
- A minimal synthetic before/after example when relevant.
- Tests and manual checks performed, including skipped checks.
- Screenshots for visible UI changes, using synthetic content only.
- Dependency, privacy, accuracy, resource-use, or compatibility tradeoffs.

Keep unrelated refactors out of the pull request and respond to review feedback.
The maintainer will review the contribution before deciding whether to merge it.
