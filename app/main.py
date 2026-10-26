from io import BytesIO
from pathlib import Path
import os
import logging
from flask import Flask, Request, request, jsonify, send_file, send_from_directory
from werkzeug.exceptions import HTTPException
from .redactor import anonymize, MAX_TEXT
from .patterns import KINDS
from .presidio_engine import status
from .extraction import extract_text, ocr_available
from .exports import export_pdf
from .errors import UserInputError, DetectionUnavailableError

class MemoryRequest(Request):
    def _get_file_stream(self, total_content_length, content_type, filename=None, content_length=None):
        return BytesIO()

def create_app(test_config=None):
    frontend = Path(__file__).resolve().parent.parent / 'frontend' / 'dist'
    app = Flask(__name__, static_folder=None)
    app.request_class = MemoryRequest
    app.config.update(MAX_CONTENT_LENGTH=11 * 1024 * 1024, MAX_FORM_MEMORY_SIZE=500000,
                      MAX_FORM_PARTS=4, TESTING=False,
                      TRUSTED_HOSTS=os.environ.get('TRUSTED_HOSTS', 'localhost,127.0.0.1,[::1]').split(','))
    logging.getLogger('pypdf').handlers = [logging.NullHandler()]
    logging.getLogger('pypdf').propagate = False
    if test_config:
        app.config.update(test_config)

    @app.before_request
    def same_origin():
        if request.method == 'POST':
            # Reject browser cross-site submissions (including multipart CSRF).
            origin = request.headers.get('Origin')
            if request.headers.get('Sec-Fetch-Site') == 'cross-site' or (origin and origin != request.host_url.rstrip('/')):
                return jsonify(error='Cross-origin requests are not allowed.'), 403

    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        return response

    @app.get('/api/health')
    def health():
        detector = status()
        return jsonify(status='ok' if detector['available'] else 'degraded',
                       local_only=True, ner=detector,
                       ocr=ocr_available(), entity_types=KINDS)

    @app.post('/api/anonymize')
    def redact():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error='Send a JSON object.'), 400
        return jsonify(anonymize(data.get('text'), data.get('mode', 'tags'), data.get('enabled')))

    @app.post('/api/extract')
    def extract():
        file = request.files.get('file')
        if file is None:
            return jsonify(error='Choose a document to upload.'), 400
        metadata = {}
        text = extract_text(file, metadata=metadata)
        return jsonify(text=text, **metadata)

    @app.post('/api/export/pdf')
    def pdf():
        data = request.get_json(silent=True)
        text = data.get('text') if isinstance(data, dict) else None
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT * 4:
            raise UserInputError('Provide valid anonymized text for export.')
        return send_file(export_pdf(text), mimetype='application/pdf', as_attachment=True, download_name='filter-anonymized.pdf')

    @app.errorhandler(UserInputError)
    def invalid(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(DetectionUnavailableError)
    def detector_unavailable(error):
        return jsonify(error=str(error)), 503

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error='File is too large (10 MB maximum).' if error.code == 413 else error.description), error.code

    @app.errorhandler(Exception)
    def failure(error):
        # Do not log parser exceptions: they may contain original document data.
        return jsonify(error='Processing failed. Check file integrity and local parser/OCR dependencies.'), 422

    @app.get('/')
    def index():
        if not (frontend / 'index.html').is_file():
            return 'Build the React frontend first: cd frontend && npm install && npm run build', 503
        return send_from_directory(frontend, 'index.html')

    @app.get('/assets/<path:name>')
    def assets(name):
        return send_from_directory(frontend / 'assets', name)

    return app

if __name__ == '__main__':
    from waitress import serve
    # Show the ready URL without enabling document/parser logging.
    logging.getLogger('waitress').setLevel(logging.INFO)
    serve(create_app(), host=os.environ.get('HOST', '127.0.0.1'), port=int(os.environ.get('PORT', '5000')),
          inbuf_overflow=12 * 1024 * 1024, max_request_body_size=11 * 1024 * 1024,
          threads=2, channel_timeout=60, ident='Filter',trusted_proxy="127.0.0.1",
trusted_proxy_headers={"x-forwarded-proto"},)
