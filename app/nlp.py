"""Explicit name/location fields for Filter's local Presidio recognizers."""
import re
from .patterns import Candidate

def contextual_entities(text):
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
    place = r"[A-ZÀ-ÖØ-Þ][\w'’-]*(?:[ \t]+[A-ZÀ-ÖØ-Þ][\w'’-]*){0,3}"
    for match in re.finditer(rf'\b(?:live[sd]?|reside[sd]?|based|located)[ \t]+in[ \t]+(?P<place>{place})', text):
        found.append(Candidate(*match.span('place'), 'LOCATION', 75))
    return found
