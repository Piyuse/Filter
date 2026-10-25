"""Infer software roles from scoped fields and usage syntax, never product lists."""
from bisect import bisect_right
import re

_FIELDS = re.compile(
    r'^\s*(?:(?:programming\s+)?languages|back\s*end|front\s*end|databases?'
    r'|(?:tools?|frameworks?|libraries|platforms?)(?:\s*(?:&|and|/)\s*(?:tools?|frameworks?|libraries|platforms?))?'
    r'|technologies|tech(?:nology)?\s+stack|technical\s+skills)\s*:', re.I)
_HEADING = re.compile(
    r'^\s*(?:(?:(?:technical|programming|software)\s+)?'
    r'(?:skills|technologies|tech(?:nology)?\s+stack)'
    r'|(?:technical|programming|software)\s+(?:expertise|summary))\s*:?\s*$', re.I)
_OTHER_FIELD = re.compile(r'^\s*[\w \t/&()-]{1,60}:')
# Personal assertions terminate a software role even inside a skills section.
_PERSONAL = re.compile(
    r'\b(?:(?:patient(?:\s+name)?|name|doctor|physician|provider|contact|city|location|state|country)\s*:'
    r'|(?:Dr|Mr|Mrs|Ms|Prof)\.\s|(?:live[sd]?|reside[sd]?|located|based)\s+in\b)', re.I)
_USE = re.compile(
    r'\b(?:using|uses?|used|built\s+(?:with|in)|developed\s+(?:with|in)'
    r'|experience\s+(?:with|in)|proficient\s+in|skilled\s+in)\s+', re.I)
_SENTENCE_END = re.compile(r'[;!?]|\.(?=\s|$)|\b(?:but|while|who|which|where)\b', re.I)
_IDENTIFIER = r'[\w+#.\u00b7-]+(?:[ \t]+[\w+#.\u00b7-]+){0,3}'
_LIST = re.compile(rf'{_IDENTIFIER}(?:[ \t]*(?:,|/|&|\band\b)[ \t]*{_IDENTIFIER})*[ \t]*')


class TechnicalContext:
    def __init__(self, text):
        spans, offset, in_section = [], 0, False
        for line in text.splitlines(keepends=True):
            value = line.strip()
            field = _FIELDS.match(line)
            if not value or (_OTHER_FIELD.match(line) and not field):
                in_section = False
            if _HEADING.fullmatch(value):
                in_section = True
            elif value.isupper() and not field:
                in_section = False
            personal = _PERSONAL.search(line)
            limit = personal.start() if personal else len(line.rstrip())
            if field:
                spans.append((offset + field.end(), offset + limit))
            elif in_section and value and _LIST.fullmatch(line[:limit].strip().rstrip(',/& ')):
                spans.append((offset, offset + limit))
            for use in _USE.finditer(line):
                personal_after = _PERSONAL.search(line, use.end())
                use_limit = personal_after.start() if personal_after else len(line.rstrip())
                tail = line[use.end():use_limit]
                stop = _SENTENCE_END.search(tail)
                end = use.end() + (stop.start() if stop else len(tail))
                if end > use.end():
                    spans.append((offset + use.end(), offset + end))
            offset += len(line)
        # Merge overlapping scopes so contains() works for nested usage phrases.
        self.spans = []
        for start, end in sorted(spans):
            if end <= start:
                continue
            if self.spans and start <= self.spans[-1][1]:
                self.spans[-1] = (self.spans[-1][0], max(end, self.spans[-1][1]))
            else:
                self.spans.append((start, end))
        self.starts = [start for start, _ in self.spans]

    def contains(self, start, end):
        index = bisect_right(self.starts, start) - 1
        return index >= 0 and end <= self.spans[index][1]
