from PIL import Image
import pytest
from app.ocr import prepare_image, recognize, OCRResult, diagnostics
from app.errors import UserInputError

def test_small_transparent_document_gets_readable_scale_and_white_matte():
    frame = prepare_image(Image.new('RGBA', (390,505), (0,0,0,0)))
    assert frame.width == 390 * 4 + 40
    assert frame.height == 505 * 4 + 40
    assert frame.getpixel((30,30)) == (255,255,255)

def test_large_document_is_not_reduced_and_extreme_shapes_are_rejected():
    frame = prepare_image(Image.new('RGB', (2000,2000), 'white'))
    assert frame.size == (2040,2040)
    with pytest.raises(UserInputError):
        prepare_image(Image.new('RGB', (1,20001), 'white'))

def line(text, box, confidence=90):
    return {'text':text, 'box':box, 'words':[{'text':word,'confidence':confidence} for word in text.split()]}

def test_sparse_pass_recovers_missing_table_without_duplicate_banner(monkeypatch):
    import app.ocr as ocr
    banner = line('EDITABLE PRINTABLE', (10,10,300,40))
    duplicate = line('EDITABLE PRINTABLE', (11,9,301,41))
    table = line('Patient: Olivia Bennett', (90,200,400,230), confidence=42)
    monkeypatch.setattr(ocr,'read_lines',lambda frame,psm,deadline: [banner] if psm==3 else [duplicate,table])
    result = recognize(Image.new('RGB',(390,505),'white'))
    assert result.text.count('EDITABLE PRINTABLE') == 1
    assert 'Patient: Olivia Bennett' in result.text
    metadata = diagnostics([result])
    assert metadata['ocr']['source_dimensions'] == [[390,505]]
    assert metadata['ocr']['low_confidence_words'] == 3
    assert any('Low-resolution' in warning for warning in metadata['warnings'])
    assert any('uncertain' in warning for warning in metadata['warnings'])

def test_sparse_timeout_keeps_successful_primary_pass(monkeypatch):
    import app.ocr as ocr
    def detect(frame,psm,deadline):
        if psm==11:
            raise RuntimeError('Tesseract process timeout')
        return [line('Patient: Olivia Bennett', (90,200,400,230))]
    monkeypatch.setattr(ocr,'read_lines',detect)
    assert 'Olivia Bennett' in recognize(Image.new('RGB',(1200,1600),'white')).text

def test_diagnostics_are_request_scoped_and_mean_confidence_is_weighted():
    result = OCRResult('example',1200,1600,.95,0,1,False)
    assert diagnostics([]) == {}
    assert diagnostics([result])['warnings'] == []
    assert diagnostics([result])['ocr']['confidence'] == .95
