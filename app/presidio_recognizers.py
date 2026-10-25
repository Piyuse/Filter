"""Presidio recognizers and NLP engine with no downloads or remote services."""
import re
import spacy
from presidio_analyzer import EntityRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import SpacyNlpEngine
from presidio_analyzer.predefined_recognizers import EmailRecognizer, SpacyRecognizer, PhoneRecognizer
from .patterns import regex_entities
from .nlp import contextual_entities
from .technical_context import TechnicalContext
from .numeric_context import NumericContext

ENTITY_TYPES = {
    'NAME': 'PERSON', 'LOCATION': 'LOCATION', 'DOB': 'DATE_OF_BIRTH',
    'DATE': 'DATE_TIME', 'EMAIL': 'EMAIL_ADDRESS', 'PHONE': 'PHONE_NUMBER',
    'SSN': 'US_SSN', 'NATIONAL_ID': 'NATIONAL_ID', 'MRN': 'MEDICAL_RECORD_NUMBER',
    'LAB_ID': 'LAB_ID', 'ADDRESS': 'STREET_ADDRESS', 'ZIP': 'POSTAL_CODE',
}


class LocalSpacyNlpEngine(SpacyNlpEngine):
    def load(self):
        # Default Presidio load() may download models. spaCy.load is local only.
        self.nlp = {model['lang_code']: spacy.load(model['model_name'], exclude=['parser', 'textcat'])
                    for model in self.models}


class OfflineEmailRecognizer(EmailRecognizer):
    def validate_result(self, pattern_text):
        # Retain the built-in regex score, including private/unlisted domains.
        # Default validation can fetch a public suffix list via tldextract.
        return None


class ContextPhoneRecognizer(PhoneRecognizer):
    def analyze(self, text, entities, nlp_artifacts=None):
        numeric = NumericContext(text)
        return [result for result in super().analyze(text, entities, nlp_artifacts)
                if numeric.accepts_phone(result.start, result.end)]


def _propagate_names(text, results, technical):
    repeated, seen = [], set()
    for result in results:
        if result.entity_type != 'PERSON':
            continue
        value = text[result.start:result.end]
        if value.casefold() in seen:
            continue
        seen.add(value.casefold())
        for match in re.finditer(r'(?<!\w)' + re.escape(value) + r'(?!\w)', text, re.I):
            if not technical.contains(match.start(), match.end()):
                repeated.append(RecognizerResult(
                    entity_type='PERSON', start=match.start(), end=match.end(),
                    score=.95 if result.recognition_metadata.get('filter_protected') else .8,
                    recognition_metadata={'filter_priority': result.recognition_metadata.get('filter_priority', 88)
                                          if result.recognition_metadata.get('filter_protected') else 58,
                                          'filter_protected': result.recognition_metadata.get('filter_protected', False)},
                ))
    return results + repeated


class ContextSpacyRecognizer(SpacyRecognizer):
    def __init__(self):
        super().__init__(supported_entities=['PERSON', 'LOCATION'], name='FilterContextSpacyRecognizer')

    def analyze(self, text, entities, nlp_artifacts=None):
        technical, results = TechnicalContext(text), []
        for result in super().analyze(text, entities, nlp_artifacts):
            # Statistical names must not consume the following field label.
            value = text[result.start:result.end].splitlines()[0].rstrip()
            result.end = result.start + len(value)
            if value and not technical.contains(result.start, result.end):
                result.recognition_metadata['filter_priority'] = 60
                results.append(result)
        return _propagate_names(text, results, technical)


class DocumentFieldsRecognizer(EntityRecognizer):
    def __init__(self):
        super().__init__(supported_entities=list(ENTITY_TYPES.values()), name='FilterDocumentFieldsRecognizer')

    def load(self):
        pass

    def analyze(self, text, entities, nlp_artifacts=None):
        # Additional document/medical patterns run inside Presidio's registry.
        results = [RecognizerResult(
            entity_type=ENTITY_TYPES[c.kind], start=c.start, end=c.end, score=.9,
            recognition_metadata={'filter_priority': c.priority, 'filter_protected': True},
        ) for c in regex_entities(text) + contextual_entities(text)
            if ENTITY_TYPES[c.kind] in entities]
        return _propagate_names(text, results, TechnicalContext(text))
