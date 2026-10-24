"""Offline spaCy NER, with a clearly reported contextual-rule fallback.

No model download occurs here. Install models separately during provisioning.
"""
import os
import re
from .patterns import Candidate

_pipeline = None
_model = os.environ.get('SPACY_MODEL', 'en_core_web_sm')
try:
    import spacy
    _pipeline = spacy.load(_model, exclude=['parser', 'lemmatizer', 'textcat'])
except (ImportError, OSError):
    pass

if os.environ.get('REQUIRE_NER') == '1' and _pipeline is None:
    raise RuntimeError('Local spaCy model is required. Install the configured SPACY_MODEL before starting.')

def status():
    return {'available': _pipeline is not None, 'model': _model if _pipeline else None,
            'engine': 'spaCy + contextual rules' if _pipeline else 'Contextual rules (limited name/location coverage)'}

def nlp_entities(text):
    found = []
    name = r"[A-ZÀ-ÖØ-Þ][a-zA-ZÀ-ÖØ-öø-ÿ'’-]+"
    patterns = [
        rf'\b(?:Patient|Patient name|Name|Physician|Doctor|Provider|Contact)\s*:\s*(?P<name>{name}(?:[ \t]+{name}){{0,3}})',
        rf'\b(?:Dr|Mr|Mrs|Ms|Prof)\.[ \t]+(?P<name>{name}(?:[ \t]+{name}){{0,2}})',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            found.append(Candidate(*match.span('name'), 'NAME', 88))
    for match in re.finditer(r'\b(?:City|Location|State|Country)\s*:\s*([^\n,;\d]{2,60})', text, re.I):
        start, end = match.span(1)
        end = start + len(text[start:end].rstrip())
        found.append(Candidate(start, end, 'LOCATION', 75))
    if _pipeline:
        for ent in _pipeline(text).ents:
            if ent.label_ in ('PERSON', 'GPE', 'LOC', 'FAC'):
                # Clinical fields often confuse statistical NER into crossing a
                # newline ("Olivia Bennett\nDate"). Keep field labels intact.
                first_line = ent.text.splitlines()[0].rstrip()
                if first_line:
                    found.append(Candidate(ent.start_char, ent.start_char + len(first_line), 'NAME' if ent.label_ == 'PERSON' else 'LOCATION', 60))
    # Propagate full contextual/NER names to repeated mentions with word boundaries.
    for entity in list(found):
        if entity.kind == 'NAME':
            value = text[entity.start:entity.end]
            for match in re.finditer(r'(?<!\w)' + re.escape(value) + r'(?!\w)', text, re.I):
                found.append(Candidate(match.start(), match.end(), 'NAME', 58))
    return found
