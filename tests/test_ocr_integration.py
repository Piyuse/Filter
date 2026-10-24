"""Exercise the real, offline OCR executable with synthetic documents."""
from io import BytesIO
from pathlib import Path
import pytest
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from app.extraction import ocr_available
from app.main import create_app

@pytest.mark.skipif(not ocr_available(), reason='Local Tesseract executable is absent')
@pytest.mark.parametrize('extension', ['jpg', 'png', 'tiff', 'pdf', 'webp'])
def test_real_ocr_and_anonymization(extension):
    image = Image.new('RGB', (1200, 300), 'white')
    path = next((p for p in ['C:/Windows/Fonts/arial.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'] if Path(p).is_file()), None)
    font = ImageFont.truetype(path, 32) if path else ImageFont.load_default(size=32)
    ImageDraw.Draw(image).multiline_text((35, 35),
        'Patient: Olivia Bennett\nDOB: 08/14/1986\nEmail: olivia.bennett@example.com',
        font=font, fill='black', spacing=18)
    stream = BytesIO()
    if extension == 'pdf':
        pdf = canvas.Canvas(stream, pagesize=(600, 150))
        pdf.drawImage(ImageReader(image), 0, 0, width=600, height=150)
        pdf.save()
    else:
        image.save(stream, format='JPEG' if extension == 'jpg' else extension.upper())
    stream.seek(0)
    client = create_app({'TESTING': True}).test_client()
    response = client.post('/api/extract', data={'file': (stream, 'clinical.' + extension)})
    assert response.status_code == 200, response.json
    for value in ['Olivia Bennett', '08/14/1986', 'olivia.bennett@example.com']:
        assert value in response.json['text']
    result = client.post('/api/anonymize', json={'text': response.json['text']})
    assert result.status_code == 200
    for value in ['Olivia Bennett', '08/14/1986', 'olivia.bennett@example.com']:
        assert value not in result.json['text']

def test_explicit_ocr_path_has_priority(monkeypatch):
    from app.extraction import find_tesseract
    monkeypatch.setenv('TESSERACT_CMD', 'D:/custom/tesseract.exe')
    assert find_tesseract() == 'D:/custom/tesseract.exe'

def test_project_ocr_install_does_not_require_path(monkeypatch):
    import app.extraction as extraction
    monkeypatch.delenv('TESSERACT_CMD', raising=False)
    monkeypatch.setattr(extraction.shutil, 'which', lambda value: None)
    monkeypatch.setattr(Path, 'is_file', lambda self: self.as_posix().endswith('/.tools/tesseract/tesseract.exe'))
    assert extraction.find_tesseract().replace('\\', '/').endswith('/.tools/tesseract/tesseract.exe')
