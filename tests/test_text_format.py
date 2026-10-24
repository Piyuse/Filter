from io import BytesIO
import pytest
from docx import Document
from reportlab.pdfgen import canvas
from pypdf import PdfReader
from app.main import create_app
from app.pdf_text import extract_pdf_page
from app.redactor import anonymize
from app.text_format import format_document_text

def test_document_whitespace_cleaning_preserves_paragraphs_and_identifiers():
    raw = '\n\n   MEDICAL SUMMARY   \r\n\r\n\r\nPatient:\tOlivia  Bennett\r\n  SSN: 482-91-7364   \n\n\nDOB:\u00a0 08/14/1986\f\nMRN: MR-209481\n\n'
    clean = format_document_text(raw)
    assert clean == 'MEDICAL SUMMARY\n\nPatient: Olivia Bennett\nSSN: 482-91-7364\n\nDOB: 08/14/1986\n\nMRN: MR-209481'
    masked = anonymize(clean)
    for value in ['Olivia Bennett', '482-91-7364', '08/14/1986', 'MR-209481']:
        assert value not in masked['text']
    for entity in masked['entities']:
        assert clean[entity['start']:entity['end']]

def test_formatting_preserves_unicode_lists_and_table_row_boundaries():
    raw = '  रोगी:  सीमा\n\n\n- Follow-up:  2 weeks\nTest\t|\tResult\nGlucose\t|\t5.2 mmol/L'
    assert format_document_text(raw) == 'रोगी: सीमा\n\n- Follow-up: 2 weeks\nTest | Result\nGlucose | 5.2 mmol/L'

def test_uploaded_docx_is_formatted_before_returning_to_ui():
    doc = Document()
    for line in ['', '   Patient:   Olivia Bennett   ', '', '', '', '   MRN:\tMR-209481   ', '']:
        doc.add_paragraph(line)
    stream = BytesIO(); doc.save(stream); stream.seek(0)
    client = create_app({'TESTING': True}).test_client()
    result = client.post('/api/extract', data={'file':(stream,'notes.docx')})
    assert result.status_code == 200
    assert result.json['text'] == 'Patient: Olivia Bennett\n\nMRN: MR-209481'

def test_plain_text_upload_is_not_reformatted():
    raw = '  Keep indentation\n\n\n  and spacing.\tColumn'
    client = create_app({'TESTING': True}).test_client()
    result = client.post('/api/extract', data={'file':(BytesIO(raw.encode()),'notes.txt')})
    assert result.json['text'] == raw

def test_pdf_upload_removes_extraction_padding_without_changing_fields():
    stream = BytesIO()
    pdf = canvas.Canvas(stream)
    pdf.drawString(50,700,'    Patient:    Olivia Bennett    ')
    pdf.drawString(50,650,'    DOB:    08/14/1986    ')
    pdf.drawString(50,600,'    MRN:    MR-209481    ')
    pdf.save(); stream.seek(0)
    result = create_app({'TESTING':True}).test_client().post('/api/extract',data={'file':(stream,'report.pdf')})
    assert result.status_code == 200
    assert [line for line in result.json['text'].splitlines() if line] == [
        'Patient: Olivia Bennett', 'DOB: 08/14/1986', 'MRN: MR-209481']


def _draw_words(pdf, words, y):
    x = 50
    for word in words:
        pdf.drawString(x, y, word)
        x += pdf.stringWidth(word) + 5


@pytest.mark.parametrize('heading_size', [12, 48])
def test_pdf_separate_word_objects_are_reconstructed_into_visual_lines(heading_size):
    stream = BytesIO()
    pdf = canvas.Canvas(stream)
    words = ['Flask,', 'REST', 'APIs,', 'and', 'relational', 'databases',
             '(MySQL,', 'MSSQL),', 'plus']
    pdf.setFont('Helvetica', heading_size)
    pdf.drawString(50, 780, 'SKILLS')
    pdf.setFont('Helvetica', 12)
    _draw_words(pdf, words, 700)
    _draw_words(pdf, ['Python', 'and', 'React.'], 680)
    pdf.drawString(50, 640, '- Local processing')
    pdf.drawString(50, 620, '- Offline OCR')
    pdf.save()
    raw = stream.getvalue()
    # Reproduce the reported failure with the previous parser, including
    # acronyms and punctuation that a sentence-joining heuristic could miss.
    assert '\n'.join(words) in PdfReader(BytesIO(raw)).pages[0].extract_text()
    client = create_app({'TESTING': True}).test_client()
    response = client.post('/api/extract', data={'file': (BytesIO(raw), 'skills.pdf')})
    assert response.status_code == 200
    text = response.json['text']
    assert [line for line in text.splitlines() if line] == [
        'SKILLS', ' '.join(words), 'Python and React.',
        '- Local processing', '- Offline OCR',
    ]
    assert '\n\n- Local processing' in text
    masked = client.post('/api/anonymize', json={'text': text})
    assert masked.status_code == 200
    assert 'Flask, REST APIs, and relational databases (MySQL, MSSQL), plus' in masked.json['text']


def test_pdf_fragmented_pii_reflows_before_detection_and_keeps_fields_separate():
    stream = BytesIO()
    pdf = canvas.Canvas(stream)
    for y, words in [
        (700, ['Patient:', 'Olivia', 'Bennett']),
        (680, ['DOB:', '08/14/1986']),
        (660, ['MRN:', 'MR-209481']),
    ]:
        _draw_words(pdf, words, y)
    pdf.showPage()
    _draw_words(pdf, ['Patient:', 'Olivia', 'Bennett'], 700)
    pdf.save(); stream.seek(0)
    client = create_app({'TESTING': True}).test_client()
    response = client.post('/api/extract', data={'file': (stream, 'clinical.pdf')})
    assert response.status_code == 200
    text = response.json['text']
    assert [line for line in text.splitlines() if line] == [
        'Patient: Olivia Bennett', 'DOB: 08/14/1986', 'MRN: MR-209481',
        'Patient: Olivia Bennett',
    ]
    assert 'MR-209481\n\nPatient:' in text
    masked = client.post('/api/anonymize', json={'text': text}).json
    for value in ['Olivia Bennett', '08/14/1986', 'MR-209481']:
        assert value not in masked['text']
    assert 'DOB: [DATE_OF_BIRTH_1]' in masked['text']
    assert masked['text'].count('Patient: [PATIENT_NAME_1]') == 2
    assert [(entity['type'], text[entity['start']:entity['end']])
            for entity in masked['entities']] == [
        ('NAME', 'Olivia Bennett'), ('DOB', '08/14/1986'), ('MRN', 'MR-209481'),
        ('NAME', 'Olivia Bennett'),
    ]


def test_pdf_rotated_text_is_not_discarded():
    stream = BytesIO()
    pdf = canvas.Canvas(stream)
    pdf.drawString(50, 700, 'Patient: Olivia Bennett')
    pdf.saveState(); pdf.translate(500, 100); pdf.rotate(90)
    pdf.drawString(0, 0, 'MRN: MR-209481')
    pdf.restoreState(); pdf.save(); stream.seek(0)
    response = create_app({'TESTING': True}).test_client().post(
        '/api/extract', data={'file': (stream, 'rotated.pdf')})
    assert response.status_code == 200
    assert 'Patient: Olivia Bennett' in response.json['text']
    assert 'MRN: MR-209481' in response.json['text']


def test_pdf_unsupported_layout_keeps_the_complete_plain_extraction(monkeypatch):
    import app.pdf_text as pdf_text

    class UnsupportedPage:
        def extract_text(self, **options):
            return 'Patient: Olivia Bennett\nMRN: MR-209481'

    def unsupported(page):
        raise ValueError('Unsupported font')

    monkeypatch.setattr(pdf_text, '_positioned_text', unsupported)
    assert extract_pdf_page(UnsupportedPage()) == 'Patient: Olivia Bennett\nMRN: MR-209481'


def test_pdf_incomplete_layout_cannot_drop_sensitive_text(monkeypatch):
    import app.pdf_text as pdf_text

    class IncompletePage:
        def extract_text(self, **options):
            return 'Patient: Olivia Bennett\nMRN: MR-209481'

    monkeypatch.setattr(pdf_text, '_positioned_text', lambda page: 'Patient: Olivia Bennett')
    assert extract_pdf_page(IncompletePage()) == 'Patient: Olivia Bennett\nMRN: MR-209481'


def test_pdf_individual_letter_objects_keep_words_and_word_spaces():
    stream = BytesIO()
    pdf = canvas.Canvas(stream)
    x = 50
    for character in 'Python and React.':
        if character != ' ':
            pdf.drawString(x, 700, character)
        x += pdf.stringWidth(character)
    pdf.save(); stream.seek(0)
    response = create_app({'TESTING': True}).test_client().post(
        '/api/extract', data={'file': (stream, 'letters.pdf')})
    assert response.status_code == 200
    assert response.json['text'] == 'Python and React.'


def test_pdf_mixed_prose_and_clinical_fields_keep_all_word_boundaries():
    stream = BytesIO()
    pdf = canvas.Canvas(stream)
    pdf.drawString(50, 750, 'TECHNICAL SUMMARY')
    lines = [
        (710, ['Flask,', 'REST', 'APIs,', 'and', 'relational', 'databases', '(MySQL,', 'MSSQL),', 'plus']),
        (690, ['Python', 'and', 'React.']),
        (640, ['Patient:', 'Olivia', 'Bennett']),
        (620, ['DOB:', '08/14/1986']),
        (600, ['MRN:', 'MR-209481']),
    ]
    for y, words in lines:
        _draw_words(pdf, words, y)
    pdf.save(); stream.seek(0)
    client = create_app({'TESTING': True}).test_client()
    response = client.post('/api/extract', data={'file': (stream, 'mixed.pdf')})
    assert response.status_code == 200
    text = response.json['text']
    assert [line for line in text.splitlines() if line] == [
        'TECHNICAL SUMMARY', *[' '.join(words) for _, words in lines],
    ]
    masked = client.post('/api/anonymize', json={'text': text}).json['text']
    assert 'Patient: [PATIENT_NAME_1]' in masked
    assert 'relational databases (MySQL, MSSQL), plus' in masked
