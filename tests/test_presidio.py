"""Privacy and precision regressions against the real local Presidio engine."""
import re
from socket import socket
import pytest
from presidio_analyzer import AnalyzerEngine
from app.main import create_app
from app.redactor import anonymize
from app import presidio_engine
from app.presidio_recognizers import LocalSpacyNlpEngine, ENTITY_TYPES
from app.technical_context import TechnicalContext

SKILLS = '''TECHNICAL SKILLS
Languages: Python, TypeScript, JavaScript, Java, C, C#
Backend: Django, Flask, REST APIs, .NET
Frontend: Angular, React, React Native, Next.js, Vite, HTML, CSS
Databases: MySQL, MSSQL
Tools & Platforms: Docker, Git, Vercel, Vercel AI SDK
Other: Agile/Scrum exposure, data migration scripting, RAG/LLM application development'''


def test_real_presidio_is_the_configured_detector():
    assert isinstance(presidio_engine._analyzer, AnalyzerEngine)
    assert not presidio_engine._analyzer.log_decision_process
    health = create_app({'TESTING': True}).test_client().get('/api/health').json
    assert health['status'] == 'ok' and health['local_only']
    assert health['ner']['engine'] == 'Microsoft Presidio (local)'
    assert health['ner']['available'] and health['ner']['version']
    assert set(ENTITY_TYPES.values()) <= set(presidio_engine._analyzer.get_supported_entities())


def test_technical_skills_from_screenshot_remain_unchanged():
    result = anonymize(SKILLS)
    assert result['text'] == SKILLS
    assert result['entities'] == []


def test_technical_skills_do_not_hide_pii_in_mixed_documents():
    text = '''Name: Olivia Bennett
Email: olivia.bennett@example.com
Phone: +1 (415) 555-0198
Location: San Francisco
''' + SKILLS + '''

Patient: James Wilson
DOB: 08/14/1986
SSN: 482-91-7364
MRN: MR-209481
Lab accession: LAB-2026-08432
Address: 2847 Maple Street
Blood pressure was 118/76 mmHg.
'''
    result = anonymize(text)
    assert SKILLS in result['text']
    assert 'Blood pressure was 118/76 mmHg.' in result['text']
    for value in ['Olivia Bennett', 'olivia.bennett@example.com', '+1 (415) 555-0198',
                  'San Francisco', 'James Wilson', '08/14/1986', '482-91-7364',
                  'MR-209481', 'LAB-2026-08432', '2847 Maple Street']:
        assert value not in result['text']


@pytest.mark.parametrize('field,value', [
    ('Patient: Java', 'Java'), ('Name: Docker', 'Docker'), ('Dr. Java', 'Java'),
    ('Location: Java', 'Java'), ('City: Go', 'Go'),
])
def test_known_software_words_in_personal_fields_are_still_sensitive(field, value):
    text = SKILLS + '\n' + field
    result = anonymize(text)
    assert SKILLS in result['text']
    assert result['text'].splitlines()[-1] != field
    assert any(text[e['start']:e['end']] == value for e in result['entities'])


def test_known_person_name_does_not_contaminate_software_references():
    text = 'Patient: Docker\n\nTools: Docker, Git, Vercel\n\nDocker reported fatigue.'
    result = anonymize(text)
    assert 'Tools: Docker, Git, Vercel' in result['text']
    assert result['text'].count('[NAME_1]') == 2


def test_real_name_and_id_inside_technical_section_still_detected():
    result = anonymize('TECHNICAL SKILLS\nJava, Flask, Patient: Olivia Bennett\nSSN: 482-91-7364')
    assert 'Java, Flask,' in result['text']
    assert 'Olivia Bennett' not in result['text']
    assert '482-91-7364' not in result['text']


def test_actual_location_is_distinct_from_software_usage():
    text = 'I live in Java and use Java. Built with Flask and React.'
    first, second = list(re.finditer('Java', text))
    context = TechnicalContext(text)
    assert not context.contains(first.start(), first.end())
    assert context.contains(second.start(), second.end())
    result = anonymize(text)
    assert result['text'] == 'I live in [LOCATION_1] and use Java. Built with Flask and React.'


@pytest.mark.parametrize('term', ['AsterForge', 'QuantaBloom', 'Zyphra UI', 'FluxWeave SDK'])
@pytest.mark.parametrize('field,kind', [('Patient', 'NAME'), ('Location', 'LOCATION')])
def test_software_role_does_not_require_a_known_product_name(term, field, kind):
    source = f'Tools & Platforms: {term}\n{field}: {term}'
    role = TechnicalContext(source)
    first = source.index(term)
    assert role.contains(first, first + len(term))
    assert not role.contains(source.rindex(term), source.rindex(term) + len(term))
    result = anonymize(source)
    assert result['text'].splitlines()[0] == f'Tools & Platforms: {term}'
    assert result['text'].splitlines()[1:] == [f'{field}: [{kind}_1]']


@pytest.mark.parametrize('text', [
    'SUMMARY\nI live in Java.',
    'TECHNICAL SKILLS\nJava, Flask\n\nI live in Java.',
    'TECHNICAL SKILLS\nJava, Flask\nEDUCATION\nI live in Java.',
])
def test_technical_context_stops_before_personal_locations(text):
    match = list(re.finditer('Java', text))[-1]
    assert not TechnicalContext(text).contains(match.start(), match.end())
    assert anonymize(text)['text'].endswith('I live in [LOCATION_1].')


def test_unicode_offsets_and_category_filters_through_presidio():
    text = '🔒\n' + SKILLS + '\n\nPatient: Olivia Bennett\nEmail: olivia@example.com'
    client = create_app({'TESTING': True}).test_client()
    result = client.post('/api/anonymize', json={'text': text}).json
    assert SKILLS in result['text']
    assert [(e['type'], text[e['start']:e['end']]) for e in result['entities']] == [
        ('NAME', 'Olivia Bennett'), ('EMAIL', 'olivia@example.com'),
    ]
    email_only = anonymize(text, enabled=['EMAIL'])
    assert 'Patient: Olivia Bennett' in email_only['text']
    assert [e['type'] for e in email_only['entities']] == ['EMAIL']
    assert anonymize(text, enabled=[])['text'] == text


def test_presidio_cold_start_and_analysis_do_not_use_network(monkeypatch):
    import spacy.cli
    import tldextract
    import requests.sessions

    def denied(*args, **kwargs):
        raise AssertionError('Presidio attempted a download, lookup or outbound connection')

    monkeypatch.setattr(socket, 'connect', denied)
    monkeypatch.setattr(spacy.cli, 'download', denied)
    monkeypatch.setattr(requests.sessions.Session, 'request', denied)
    monkeypatch.setattr(tldextract, 'extract', denied)
    engine = presidio_engine._build_analyzer()
    text = 'Patient: Olivia Bennett\nEmail: alice@private.invalid\nPhone: +1 (415) 555-0198\nMRN: MR-209481'
    results = engine.analyze(text=text, language='en')
    assert {'PERSON', 'EMAIL_ADDRESS', 'PHONE_NUMBER', 'MEDICAL_RECORD_NUMBER'} <= {r.entity_type for r in results}


def test_missing_model_fails_locally_without_attempting_download(monkeypatch):
    import spacy.cli

    def denied(*args, **kwargs):
        raise AssertionError('Missing model must not trigger a runtime download')

    monkeypatch.setattr(spacy.cli, 'download', denied)
    engine = LocalSpacyNlpEngine(models=[{'lang_code': 'en', 'model_name': 'filter_missing_model_test'}])
    with pytest.raises(OSError):
        engine.load()


def test_unavailable_presidio_returns_503_and_no_original_text(monkeypatch):
    monkeypatch.setattr(presidio_engine, '_analyzer', None)
    client = create_app({'TESTING': True}).test_client()
    assert client.get('/api/health').json['status'] == 'degraded'
    response = client.post('/api/anonymize', json={'text': 'Patient: secret-person-name'})
    assert response.status_code == 503
    assert 'Microsoft Presidio' in response.json['error']
    assert b'secret-person-name' not in response.data
    assert 'text' not in response.json


def test_presidio_does_not_log_document_contents(caplog):
    with caplog.at_level('DEBUG', logger='presidio-analyzer'):
        anonymize('Patient: Olivia Bennett\nEmail: olivia.bennett@example.com')
    assert 'Olivia Bennett' not in caplog.text
    assert 'olivia.bennett@example.com' not in caplog.text
