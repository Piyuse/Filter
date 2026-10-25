"""Local detection rules. Offsets always refer to the unmodified original text."""
import re
from dataclasses import dataclass
from .numeric_context import NumericContext

@dataclass(frozen=True)
class Candidate:
    start: int
    end: int
    kind: str
    priority: int = 50
    protected: bool = False

KINDS = ('NAME', 'DOB', 'DATE', 'EMAIL', 'PHONE', 'SSN', 'NATIONAL_ID', 'MRN', 'LAB_ID', 'ADDRESS', 'LOCATION', 'ZIP', 'SECRET')
MONTH = r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
DATE = rf'\b(?:\d{{4}}[/-]\d{{1,2}}[/-]\d{{1,2}}|\d{{1,2}}[./-]\d{{1,2}}[./-]\d{{2,4}}|{MONTH}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}|\d{{1,2}}\s+{MONTH}\.?\s+\d{{4}})\b'
RULES = [
    ('SSN', r'\b\d{3}-\d{2}-\d{4}\b', 100),
    ('SSN', r'\b(?:SSN|social security(?: number)?)\s*[:#=-]?\s*(?P<value>\d{9})\b', 100),
    ('NATIONAL_ID', r'\b\d{4}[ -]\d{4}[ -]\d{4}\b|\b[A-Z]{5}\d{4}[A-Z]\b', 92),
    ('EMAIL', r'(?<![\w.%+-])[\w.%+-]+@[\w.-]+\.[a-zA-Z]{2,}\b', 95),
    ('NATIONAL_ID', r'\b(?:national\s*(?:id|identification)(?:\s*(?:number|no\.?))?|passport(?:\s*(?:number|no\.?))?|aadhaar|aadhar|SSN|social security(?: number)?)\s*[:#=-]?\s*(?P<value>[A-Z0-9][A-Z0-9 -]{4,24}[A-Z0-9])\b', 96),
    ('MRN', r'\b(?:MRN|medical\s*record(?:\s*(?:number|no\.?))?)\s*[:#=-]?\s*(?P<value>[A-Z0-9][A-Z0-9-]{2,29})\b', 96),
    ('LAB_ID', r'\b(?:lab(?:\s*accession)?(?:\s*(?:id|number|no\.?))?|accession(?:\s*(?:number|no\.?))?|sample(?:\s*(?:id|number|no\.?))?|barcode(?:\s*(?:id|number))?)\s*[:#=-]?\s*(?P<value>(?=[A-Z0-9-]{0,39}\d)[A-Z0-9][A-Z0-9-]{2,39})\b', 96),
    ('DOB', rf'\b(?:DOB|date\s*of\s*birth|born)\s*[:=-]?\s*(?P<value>{DATE})', 99),
    ('DATE', DATE, 80),
    ('PHONE', r'(?<!\w)(?:\+\d{1,3}[ .-]?)?(?:\(\d{2,4}\)|\d{2,4})[ .-]\d{3,4}[ .-]\d{3,4}(?:\s*(?:ext\.?|x)\s*\d{1,6})?(?!\w)|(?<!\w)\+\d{10,15}\b|\b\d{10}\b', 70),
    ('PHONE', r'(?<!\w)\+\d{1,3}(?:[ .()-]*\d){7,14}(?!\w)|\b\d{3}-\d{4}\b', 69),
    ('ADDRESS', r'\b\d{1,6}[ \t]+(?:[\w.\'-]+[ \t]+){0,7}(?:Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Drive|Dr|Boulevard|Blvd|Court|Ct|Way|Place|Pl|Terrace|Parkway)\b\.?[ \t]*(?:(?:Apt|Suite|Unit|#)[ \t]*[\w-]+)?', 85),
    ('ZIP', r'\b(?:ZIP(?:\s*code)?|postal(?:\s*code)?|postcode|PIN(?:\s*code)?)\s*[:=-]?\s*(?P<value>\d{5}(?:-\d{4})?|\d{6}|[A-Z]\d[A-Z]\s?\d[A-Z]\d|[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\b', 90),
    ('ZIP', r'\b\d{5}(?:-\d{4})?\b|\b[A-Z]{1,2}\d[A-Z\d]?\s+\d[A-Z]{2}\b', 40),
]

def regex_entities(text):
    found = []
    numeric = NumericContext(text)
    for kind, pattern, priority in RULES:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            start, end = match.span('value') if 'value' in match.re.groupindex else match.span()
            while end > start and text[end - 1].isspace():
                end -= 1
            if kind == 'PHONE' and not numeric.accepts_phone(start, end):
                continue
            if kind == 'ZIP' and priority == 40 and numeric.is_measurement(start, end):
                continue
            found.append(Candidate(start, end, kind, priority))
    return found
