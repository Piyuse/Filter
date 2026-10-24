"""Offline OCR preprocessing, layout recovery and quality diagnostics.

No language-model correction is applied: uncertain identifiers must remain
uncertain rather than being replaced with plausible invented values.
"""
from dataclasses import dataclass
from collections import defaultdict
import math
import os
import time
from PIL import Image, ImageOps
import pytesseract
from .errors import UserInputError

@dataclass
class OCRResult:
    text: str
    width: int
    height: int
    confidence: float
    low_confidence_words: int
    words: int
    low_resolution: bool

def prepare_image(image):
    if max(image.size) > 20000:
        raise UserInputError('Image dimensions must be at most 20,000 pixels per side.')
    frame = ImageOps.exif_transpose(image)
    # Flatten transparency onto white rather than converting it to black.
    if frame.mode in ('RGBA', 'LA') or 'transparency' in frame.info:
        rgba = frame.convert('RGBA')
        frame = Image.new('RGB', rgba.size, 'white')
        frame.paste(rgba, mask=rgba.getchannel('A'))
    else:
        frame = frame.convert('RGB')
    # Small screenshots otherwise cause automatic segmentation to ignore whole
    # tables. Preserve colour because grayscale can erase coloured headings.
    factor = min(4.0, 1800 / frame.width, math.sqrt(8_000_000 / (frame.width * frame.height)))
    if factor > 1.05:
        frame = frame.resize((round(frame.width * factor), round(frame.height * factor)), Image.Resampling.LANCZOS)
    border = 20 if (frame.width + 40) * (frame.height + 40) <= 20_000_000 else 0
    return ImageOps.expand(frame, border=border, fill='white')

def read_lines(frame, psm, deadline):
    remaining = deadline - time.monotonic()
    if remaining < 0.2:
        return []
    data = pytesseract.image_to_data(frame, lang=os.environ.get('OCR_LANG', 'eng'),
        config=f'--oem 1 --psm {psm} --dpi 300',
        output_type=pytesseract.Output.DICT, timeout=remaining)
    grouped = defaultdict(list)
    for i, value in enumerate(data['text']):
        value = value.strip()
        confidence = float(data['conf'][i])
        if not value or confidence < 0:
            continue
        key = (data['block_num'][i], data['par_num'][i], data['line_num'][i])
        grouped[key].append({'text': value, 'confidence': confidence,
            'x': data['left'][i], 'y': data['top'][i],
            'w': data['width'][i], 'h': data['height'][i]})
    lines = []
    for words in grouped.values():
        if not any(any(c.isalnum() for c in word['text']) for word in words):
            continue
        x, y = min(w['x'] for w in words), min(w['y'] for w in words)
        right = max(w['x'] + w['w'] for w in words)
        bottom = max(w['y'] + w['h'] for w in words)
        lines.append({'words': words, 'text': ' '.join(w['text'] for w in words),
                      'box': (x, y, right, bottom)})
    return lines

def overlap(a, b):
    ax, ay, ar, ab = a
    bx, by, br, bb = b
    intersection = max(0, min(ar, br) - max(ax, bx)) * max(0, min(ab, bb) - max(ay, by))
    return intersection / max(1, min((ar - ax) * (ab - ay), (br - bx) * (bb - by)))

def recognize(image):
    width, height = image.size
    deadline = time.monotonic() + 30
    frame = prepare_image(image)
    lines = read_lines(frame, 3, deadline)
    # Sparse-layout detection recovers isolated fields missed by page analysis.
    # Add only new spatial regions, never concatenate duplicate whole-page OCR.
    try:
        extra = read_lines(frame, 11, deadline)
    except RuntimeError:
        if not lines:
            raise
        extra = []
    for line in extra:
        if any(overlap(line['box'], known['box']) >= 0.25 for known in lines):
            continue
        if max(w['confidence'] for w in line['words']) >= 35:
            lines.append(line)
    lines.sort(key=lambda line: (line['box'][1], line['box'][0]))
    words = [word for line in lines for word in line['words'] if any(c.isalnum() for c in word['text'])]
    confidence = sum(w['confidence'] for w in words) / (100 * len(words)) if words else 0
    return OCRResult(text='\n'.join(line['text'] for line in lines), width=width, height=height,
        confidence=round(confidence, 3), low_confidence_words=sum(w['confidence'] < 60 for w in words),
        words=len(words), low_resolution=width < 800 and height < 1200)

def diagnostics(results):
    if not results:
        return {}
    warnings = []
    small = next((r for r in results if r.low_resolution), None)
    if small:
        warnings.append(f'Low-resolution source ({small.width} × {small.height} pixels). Small or blurred text may be missing or misread. Use the original PDF or a higher-resolution scan when available.')
    uncertain = sum(r.low_confidence_words for r in results)
    if uncertain:
        warnings.append(f'OCR flagged {uncertain} uncertain words. Check names, dates, IDs and table fields against the source before anonymizing or sharing. Detection may miss misread identifiers.')
    count = sum(r.words for r in results)
    confidence = sum(r.confidence * r.words for r in results) / max(1, count)
    return {'warnings': warnings, 'ocr': {'confidence': round(confidence, 3),
        'pages': len(results), 'low_confidence_words': uncertain,
        'source_dimensions': [[r.width, r.height] for r in results],
        'note': 'Tesseract word confidence is an estimate, not proof of complete or accurate extraction.'}}
