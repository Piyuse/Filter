"""Public API response types; no extra runtime validation dependency."""
from typing import TypedDict

class Entity(TypedDict):
    start: int
    end: int
    type: str
    replacement: str

class Language(TypedDict):
    code: str
    confidence: float
    note: str

class RedactResponse(TypedDict):
    text: str
    entities: list[Entity]
    counts: dict[str, int]
    language: Language
    warnings: list[str]
    ner: dict
