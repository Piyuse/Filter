"""Create text-only PDFs. Original files and metadata are never copied."""
from io import BytesIO
from pathlib import Path
import os
from xml.sax.saxutils import escape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def export_pdf(text):
    font = 'Helvetica'
    candidates = [os.environ.get('PDF_FONT', ''), 'C:/Windows/Fonts/arial.ttf',
                  '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/Library/Fonts/Arial.ttf']
    for path in candidates:
        if path and Path(path).is_file():
            if 'LocalUnicode' not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont('LocalUnicode', path))
            font = 'LocalUnicode'
            break
    buffer = BytesIO()
    style = ParagraphStyle('text', fontName=font, fontSize=10, leading=16, wordWrap='CJK')
    story = []
    for line in text.split('\n'):
        story.extend([Paragraph(escape(line) or ' ', style), Spacer(1, 4)])
    SimpleDocTemplate(buffer, title='Anonymized document', author='Veil',
        leftMargin=48, rightMargin=48, topMargin=48, bottomMargin=48).build(story)
    buffer.seek(0)
    return buffer
