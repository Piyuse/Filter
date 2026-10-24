"""Reconstruct PDF lines locally from text positions, before PII detection."""
from collections import Counter


def _characters(text):
    return Counter(character for character in text if not character.isspace())


def _positioned_text(page):
    # Use pypdf 6's font/transform-aware layout groups, but render spaces using
    # each run's actual ending position. Its fixed-width page renderer uses a
    # page-wide average character width, which can glue words together when
    # headings, narrow letters and body fonts have different widths.
    from pypdf.generic import ContentStream
    from pypdf._text_extraction._layout_mode import (
        text_show_operations, y_coordinate_groups,
    )

    content = page.get_contents()
    if content is None:
        return ''
    groups = text_show_operations(
        iter(ContentStream(content, page.pdf, 'bytes').operations),
        page._layout_mode_fonts(), strip_rotated=False,
    )
    if not groups:
        return ''
    lines = []
    previous_y = previous_height = None
    for y, runs in y_coordinate_groups(groups).items():
        height = max(run['font_height'] for run in runs)
        if lines:
            # Preserve paragraph gaps, without reproducing pages of padding.
            paragraph_gap = max(height, previous_height, 1) * 2
            lines.append('\n\n' if abs(y - previous_y) >= paragraph_gap else '\n')
        end_x = font_height = None
        for run in runs:
            if end_x is not None:
                # Ignore tiny kerning/rounding gaps between separately drawn
                # letters; actual inter-word gaps become exactly one space.
                tolerance = max(min(font_height, run['font_height']) * .1, .1)
                if run['tx'] - end_x > tolerance:
                    lines.append(' ')
            lines.append(run['text'])
            end_x, font_height = run['displaced_tx'], run['font_height']
        previous_y, previous_height = y, height
    return ''.join(lines)


def extract_pdf_page(page):
    plain = page.extract_text() or ''
    if not plain.strip():
        return plain
    try:
        # PDF generators often draw each word in its own text object. Plain
        # extraction inserts a newline after each object, even on one baseline.
        layout = _positioned_text(page)
    except Exception:
        # Some PDF fonts/transforms are unsupported by layout extraction.
        # Keep the original local extraction without logging document contents.
        return plain
    # Position reconstruction must not silently lose any non-whitespace text.
    # Ordering may change to match the page, so compare character counts.
    return layout if _characters(layout) == _characters(plain) else plain
