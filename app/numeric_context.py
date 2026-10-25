"""Validate numeric entity hypotheses using syntax, units and phone metadata.

No analyte names, software names or document-specific values are looked up.
Spans refer to the original text so a rejected hypothesis cannot expand a mask.
"""
import re
from bisect import bisect_right
import phonenumbers

REGIONS = ('US', 'GB', 'DE', 'FR', 'IL', 'IN', 'CA', 'BR')
_NUMBER = r'[+−-]?\d+(?:[.,]\d+)?(?:[eE][+-]?\d+)?'
_RANGE = rf'{_NUMBER}[ \t]*(?:[-–—]|\bto\b)[ \t]*{_NUMBER}'
# Dimensional syntax, rather than a list of known medical units. A plain word
# such as "now" after a phone number must not be interpreted as a unit.
_ATOM = r'[a-zA-ZµμΩ°]+(?:\^?[+-]?\d+|[⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]+)?'
_UNIT = rf'(?:(?:{_ATOM}|1|10(?:\^\d+|[⁰¹²³⁴⁵⁶⁷⁸⁹]+))[ \t]*[/·*][ \t]*{_ATOM}(?:[/·*]{_ATOM})*|{_ATOM}(?:\^[+-]?\d+|[²³])|%|°[CFK])'
_MEASUREMENTS = re.compile(
    rf'(?<![\w.+-])(?:{_NUMBER}[ \t]+{_RANGE}|{_RANGE}[ \t]+{_NUMBER}|{_RANGE}|{_NUMBER})'
    rf'[ \t]*{_UNIT}(?!\w)', re.I)
_CONTACT_LABEL = re.compile(
    r'\b(?:phone|telephone|tel|mobile|cell(?:phone)?|fax|call|contact[ \t]+number)'
    r'(?:[ \t]+(?:number|no\.?))?[ \t]*[:#=.-]?[ \t]*$', re.I)
_LOCAL = re.compile(r'\d{3}-\d{4}(?:[ \t]*(?:ext\.?|x)[ \t]*\d{1,6})?', re.I)


class NumericContext:
    def __init__(self, text):
        self.text = text
        self.measurements = [m.span() for m in _MEASUREMENTS.finditer(text)]
        self.starts = [start for start, _ in self.measurements]

    def is_measurement(self, start, end):
        index = bisect_right(self.starts, start) - 1
        return index >= 0 and end <= self.measurements[index][1]

    def accepts_phone(self, start, end):
        value = self.text[start:end]
        before = self.text[max(self.text.rfind('\n', 0, start) + 1, start - 80):start]
        labeled = bool(_CONTACT_LABEL.search(before))
        # A nearby phone elsewhere in a report must not override a lab row.
        if not labeled and self.is_measurement(start, end):
            return False
        regions = (None,) if value.startswith('+') else REGIONS
        if labeled or value.startswith('+'):
            # Possible-length validation also supports fictional/test numbers;
            # it does not claim a number is assigned or reachable.
            for region in regions:
                try:
                    if phonenumbers.is_possible_number(phonenumbers.parse(value, region)):
                        return True
                except phonenumbers.NumberParseException:
                    pass
            return False
        if _LOCAL.fullmatch(value):
            return True
        # Validate the entire candidate, including digit grouping. A permissive
        # parser can reinterpret "139 136-145" as a French national number.
        for region in regions:
            for match in phonenumbers.PhoneNumberMatcher(
                    value, region, leniency=phonenumbers.Leniency.STRICT_GROUPING):
                if match.start == 0 and match.end == len(value):
                    return True
        return False
