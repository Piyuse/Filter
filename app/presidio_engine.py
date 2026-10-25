"""Single local detection entry point: Microsoft Presidio Analyzer."""
from importlib.metadata import version
import logging
import os
from .patterns import Candidate
from .errors import DetectionUnavailableError

# Presidio's context enhancer can log surrounding tokens at DEBUG even with
# decision tracing disabled. Suppress library logging at the source and stop
# child logger propagation; original documents must never enter application logs.
for _logger_name in ('presidio-analyzer', 'presidio_analyzer'):
    _logger = logging.getLogger(_logger_name)
    _logger.handlers = [logging.NullHandler()]
    _logger.propagate = False
    _logger.disabled = True

_model = os.environ.get('SPACY_MODEL', 'en_core_web_sm')
_analyzer = None
_version = None
_setup_message = ('Microsoft Presidio or its local NLP model is unavailable. '
                  'Install requirements-ner.txt in the project virtual environment and restart Filter.')


def _build_analyzer():
    from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
    from presidio_analyzer.nlp_engine import NerModelConfiguration
    from presidio_analyzer.predefined_recognizers import UsSsnRecognizer
    from .presidio_recognizers import (
        LocalSpacyNlpEngine, OfflineEmailRecognizer, ContextSpacyRecognizer, DocumentFieldsRecognizer,
        ContextPhoneRecognizer,
    )
    config = NerModelConfiguration(
        model_to_presidio_entity_mapping={'PERSON': 'PERSON', 'GPE': 'LOCATION', 'LOC': 'LOCATION', 'FAC': 'LOCATION'},
        labels_to_ignore=['ORG', 'NORP', 'DATE', 'TIME', 'PERCENT', 'MONEY', 'QUANTITY',
                          'ORDINAL', 'CARDINAL', 'PRODUCT', 'EVENT', 'WORK_OF_ART', 'LAW', 'LANGUAGE'],
    )
    engine = LocalSpacyNlpEngine(
        models=[{'lang_code': 'en', 'model_name': _model}], ner_model_configuration=config,
    )
    engine.load()
    registry = RecognizerRegistry(supported_languages=['en'])
    for recognizer in [ContextSpacyRecognizer(), OfflineEmailRecognizer(), ContextPhoneRecognizer(),
                       UsSsnRecognizer(), DocumentFieldsRecognizer()]:
        registry.add_recognizer(recognizer)
    return AnalyzerEngine(nlp_engine=engine, registry=registry, supported_languages=['en'],
                          default_score_threshold=.5, log_decision_process=False)


try:
    _analyzer = _build_analyzer()
    _version = version('presidio-analyzer')
except (ImportError, OSError):
    # Inspectable via health/UI; never silently switch to weaker detection.
    pass

if os.environ.get('REQUIRE_NER') == '1' and _analyzer is None:
    raise RuntimeError(_setup_message)


def status():
    return {'available': _analyzer is not None, 'engine': 'Microsoft Presidio (local)',
            'model': _model if _analyzer is not None else None, 'version': _version,
            'languages': ['en'], 'score_threshold': .5,
            'error': None if _analyzer is not None else _setup_message}


def presidio_entities(text, enabled):
    if _analyzer is None:
        raise DetectionUnavailableError(_setup_message)
    if not enabled:
        return []
    from .presidio_recognizers import ENTITY_TYPES
    requested = [ENTITY_TYPES[kind] for kind in enabled if kind in ENTITY_TYPES]
    if not requested:
        return []
    to_kind = {value: key for key, value in ENTITY_TYPES.items()}
    results = _analyzer.analyze(text=text, language='en',
                                entities=requested,
                                return_decision_process=False)
    priorities = {'SSN': 100, 'EMAIL': 95, 'PHONE': 70, 'NAME': 60, 'LOCATION': 60}
    return [Candidate(result.start, result.end, to_kind[result.entity_type],
                      result.recognition_metadata.get('filter_priority', priorities.get(to_kind[result.entity_type], 50)),
                      result.recognition_metadata.get('filter_protected', False)
                      or to_kind[result.entity_type] not in ('NAME', 'LOCATION'))
            for result in results if result.entity_type in to_kind]
