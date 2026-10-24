"""Resolve overlaps before substituting; never edit text while detecting."""
from collections import Counter
from .patterns import regex_entities, KINDS
from .nlp import nlp_entities, status
from .language import detect_language
from .schemas import RedactResponse
from .errors import UserInputError

MAX_TEXT = 100000

def anonymize(text, mode='tags', enabled=None) -> RedactResponse:
    if not isinstance(text, str) or not text.strip():
        raise UserInputError('Enter some text to anonymize.')
    if len(text) > MAX_TEXT:
        raise UserInputError('Text is limited to 100,000 characters.')
    if mode not in ('tags', 'redact', 'blocks'):
        raise UserInputError('Unknown masking format.')
    if enabled is None:
        enabled = list(KINDS)
    if not isinstance(enabled, list) or any(kind not in KINDS for kind in enabled):
        raise UserInputError('Invalid entity types.')
    candidates = regex_entities(text) + nlp_entities(text)
    # Split into connected overlap groups, select the highest priority in each,
    # and mask the union so a partial NER overlap cannot leave a suffix visible.
    ordered = sorted((c for c in candidates if c.kind in enabled), key=lambda c: (c.start, c.end))
    groups = []
    for candidate in ordered:
        if groups and candidate.start < groups[-1]['end']:
            group = groups[-1]
            group['end'] = max(group['end'], candidate.end)
            if candidate.priority > group['winner'].priority:
                group['winner'] = candidate
        else:
            groups.append({'start': candidate.start, 'end': candidate.end, 'winner': candidate})
    counters, tokens, entities, output = Counter(), {}, [], []
    cursor = 0
    for group in groups:
        start, end, kind = group['start'], group['end'], group['winner'].kind
        key = (kind, text[start:end].casefold())
        if key not in tokens:
            counters[kind] += 1
            label = {'NAME': 'PATIENT_NAME', 'DOB': 'DATE_OF_BIRTH', 'SSN': 'SSN_MASKED'}.get(kind, kind)
            tokens[key] = f'[{label}_{counters[kind]}]'
        replacement = tokens[key] if mode == 'tags' else '[REDACTED]' if mode == 'redact' else '█████'
        output.extend((text[cursor:start], replacement))
        entities.append({'start': start, 'end': end, 'type': kind, 'replacement': replacement})
        cursor = end
    output.append(text[cursor:])
    warnings = []
    if not status()['available']:
        warnings.append('Local spaCy model is not installed. Names and locations use limited contextual rules. Install the model for broader coverage.')
    language = detect_language(text)
    if language['code'] not in ('en', 'und'):
        warnings.append('Rules primarily target English documents. Language detection does not imply NER support for this language.')
    return {'text': ''.join(output), 'entities': entities, 'counts': dict(Counter(e['type'] for e in entities)),
            'language': language, 'warnings': warnings, 'ner': status()}
