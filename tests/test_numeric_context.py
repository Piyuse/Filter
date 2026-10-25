"""Numeric precision checks use arbitrary labels, not a clinical-name dictionary."""
from socket import socket
import pytest
from app.numeric_context import NumericContext
from app.patterns import regex_entities
from app.presidio_recognizers import ContextPhoneRecognizer, DocumentFieldsRecognizer
from app.redactor import anonymize
from app.main import create_app


@pytest.mark.parametrize('text', [
    '139 136-145 mEq/L', '139 136 – 145 mEq/L', '139 136 to 145 mEq/L',
    '3.9 3.5-5.1 mEq/L', '100 98-107 mEq/L', '5.9 5.7 - 8.2 g/dL',
    '123 456-7890 mg/L', '415 555-0198 ng/mL', '12345 12000-15000 U/L',
    '12345 mg/L', '12345 %', '12345 12000-15000 kg/m3',
    '12345 12000-15000 1/µL', '12345 12000-15000 10^9/L',
    '12345 12000-15000 10⁹/L',
])
def test_dimensional_measurements_are_not_contact_numbers(text):
    # A made-up label demonstrates that no known analyte name is required.
    source = 'Xyq-42: ' + text
    result = anonymize(source, enabled=['PHONE', 'ZIP'])
    assert result['text'] == source
    assert result['entities'] == []


@pytest.mark.parametrize('source', [
    'Sodium 139 136-145 mEq/L', '139 136-145',
    'RandomReading 139 136-145 mEq/L\nPhone: +1 (415) 555-0198',
])
def test_bad_grouping_cannot_become_a_protected_phone(source):
    candidates = regex_entities(source)
    assert not any(c.kind == 'PHONE' and source[c.start:c.end] == '139 136-145'
                   for c in candidates)
    for recognizer in [ContextPhoneRecognizer(), DocumentFieldsRecognizer()]:
        results = recognizer.analyze(source, entities=['PHONE_NUMBER'])
        assert not any(source[r.start:r.end] == '139 136-145' for r in results)


@pytest.mark.parametrize('phone', [
    '+1 (415) 555-0198', '+91 98765 43210', '+44 20 7946 0958',
    '415 555-0198', '4155550198', '555-0198', '+81 90 1234 5678',
    '020 7946 0958', 'Phone: 123 456-7890', 'Fax: 415-555-0198 ext. 42',
])
def test_real_phone_formats_are_still_masked(phone):
    result = anonymize(phone, enabled=['PHONE'])
    assert result['counts']['PHONE'] == 1
    assert '[PHONE_1]' in result['text']
    assert result['entities'][0]['end'] == len(phone)


def test_phone_later_on_same_line_is_not_suppressed_by_a_measurement():
    source = '139 136-145 mEq/L; call 415 555-0198 now.'
    result = anonymize(source, enabled=['PHONE'])
    assert result['text'] == '139 136-145 mEq/L; call [PHONE_1] now.'


def test_explicit_identifier_fields_remain_private_near_lab_results():
    source = ('Patient: Olivia Bennett\nMRN: MR-209481\nSSN: 482-91-7364\n'
              'Email: olivia@example.com\nPhone: +1 (415) 555-0198\n'
              'Sodium 139 136-145 mEq/L\nPotassium 3.9 3.5-5.1 mEq/L')
    result = anonymize(source)
    for value in ['Olivia Bennett', 'MR-209481', '482-91-7364', 'olivia@example.com',
                  '+1 (415) 555-0198']:
        assert value not in result['text']
    assert result['text'].endswith('Sodium 139 136-145 mEq/L\nPotassium 3.9 3.5-5.1 mEq/L')


def test_regression_through_http_endpoint_without_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError('Numeric validation must stay offline')
    monkeypatch.setattr(socket, 'connect', denied)
    client = create_app({'TESTING': True}).test_client()
    source = ('Total Protein 5.9 5.7 - 8.2 g/dL\nBiuret\nAlbumin 4.1 3.2-4.8 g/dL\nBCG\n'
              'Sodium 139 136-145 mEq/L\nIndirect ISE\nPotassium 3.9 3.5-5.1 mEq/L\n'
              'Indirect ISE\nChloride 100 98-107 mEq/L')
    response = client.post('/api/anonymize', json={'text': source})
    assert response.status_code == 200
    assert response.json['text'] == source
    assert response.json['entities'] == []
