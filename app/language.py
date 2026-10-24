"""Deterministically seeded local statistical language identification."""
from langdetect import DetectorFactory, detect_langs, LangDetectException
DetectorFactory.seed = 0

def detect_language(text):
    if sum(c.isalpha() for c in text) < 20:
        return {'code': 'und', 'confidence': 0, 'note': 'Too little text for reliable language detection.'}
    try:
        result = detect_langs(text[:20000])[0]
        return {'code': result.lang, 'confidence': round(result.prob, 4),
                'note': 'Statistical estimate; confidence is not a guarantee of accuracy.'}
    except LangDetectException:
        return {'code': 'und', 'confidence': 0, 'note': 'Language could not be identified.'}
