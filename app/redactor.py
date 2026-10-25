"""Resolve overlaps before substituting; never edit text while detecting."""
from collections import Counter
from .patterns import KINDS
from .presidio_engine import presidio_entities, status
from .language import detect_language
from .schemas import RedactResponse
from .errors import UserInputError

MAX_TEXT = 100000

def anonymize(text, mode='tags', enabled=None, use_local_llm=False) -> RedactResponse:
    if not isinstance(text, str) or not text.strip():
        raise UserInputError('Enter some text to anonymize.')
    if len(text) > MAX_TEXT:
        raise UserInputError('Text is limited to 100,000 characters.')
    if mode not in ('tags', 'redact', 'blocks'):
        raise UserInputError('Unknown masking format.')
    if type(use_local_llm) is not bool:
        raise UserInputError('Local AI review must be true or false.')
    if enabled is None:
        enabled = list(KINDS)
    if not isinstance(enabled, list) or any(kind not in KINDS for kind in enabled):
        raise UserInputError('Invalid entity types.')
    candidates = presidio_entities(text, enabled)
    review = {'used': False}
    if use_local_llm and enabled:
        from .local_llm import review as review_locally
        candidates, review = review_locally(text, candidates, enabled)
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
            label = {'DOB': 'DATE_OF_BIRTH', 'SSN': 'SSN_MASKED'}.get(kind, kind)
            tokens[key] = f'[{label}_{counters[kind]}]'
        replacement = tokens[key] if mode == 'tags' else '[REDACTED]' if mode == 'redact' else '█████'
        output.extend((text[cursor:start], replacement))
        entities.append({'start': start, 'end': end, 'type': kind, 'replacement': replacement})
        cursor = end
    output.append(text[cursor:])
    warnings = []
    language = detect_language(text)
    if language['code'] not in ('en', 'und'):
        warnings.append('The installed Presidio NLP model supports English. Language detection does not imply NER support for this language.')
    return {'text': ''.join(output), 'entities': entities, 'counts': dict(Counter(e['type'] for e in entities)),
            'language': language, 'warnings': warnings, 'ner': status(), 'review': review}
