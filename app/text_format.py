"""Clean extraction whitespace before detection, without rewriting document text."""
import re

def format_document_text(text):
    # Preserve hard line/paragraph boundaries and all non-whitespace characters.
    # PDF words are already grouped by page position in pdf_text.py. Never guess
    # which remaining lines to join: clinical fields and rows need boundaries.
    text = text.replace('\r\n', '\n').replace('\r', '\n').replace('\f', '\n\n')
    lines = [re.sub(r'[ \t\u00a0]+', ' ', line).strip(' ') for line in text.split('\n')]
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip('\n')
