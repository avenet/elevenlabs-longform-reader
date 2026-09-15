import re

from app.config import settings

HEADING_RE = re.compile(
    r"^(chapter\s+\d+|part\s+[ivxlcdm\d]+|section\s+\d+|#{1,6}\s+.+)$",
    re.IGNORECASE,
)
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'])")


def _is_heading(paragraph: str) -> bool:
    stripped = paragraph.strip()
    if not stripped:
        return False
    if len(stripped) > 120:
        return False
    if HEADING_RE.match(stripped):
        return True
    if stripped.isupper() and len(stripped.split()) <= 12:
        return True
    return False


def _split_sentences(text: str) -> list[str]:
    parts = SENTENCE_RE.split(text.strip())
    return [part.strip() for part in parts if part.strip()]


def _pack_units(units: list[str], target: int, maximum: int) -> list[str]:
    sections: list[str] = []
    current: list[str] = []
    current_len = 0

    for unit in units:
        unit_len = len(unit)
        separator = 2 if current else 0
        projected = current_len + separator + unit_len

        if current and projected > maximum:
            sections.append("\n\n".join(current))
            current = [unit]
            current_len = unit_len
            continue

        if current and projected > target and current_len >= target // 2:
            sections.append("\n\n".join(current))
            current = [unit]
            current_len = unit_len
            continue

        if not current and unit_len > maximum:
            sentences = _split_sentences(unit)
            if len(sentences) > 1:
                sections.extend(_pack_units(sentences, target, maximum))
            else:
                for start in range(0, unit_len, maximum):
                    sections.append(unit[start : start + maximum].strip())
            current = []
            current_len = 0
            continue

        current.append(unit)
        current_len = projected if separator else unit_len

    if current:
        sections.append("\n\n".join(current))

    return [section for section in sections if section.strip()]


def split_text(
    text: str,
    target_chars: int | None = None,
    max_chars: int | None = None,
) -> list[str]:
    target = target_chars or settings.section_target_chars
    maximum = max_chars or settings.section_max_chars

    raw_paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not raw_paragraphs:
        return []

    units: list[str] = []
    pending_heading: str | None = None

    for paragraph in raw_paragraphs:
        if _is_heading(paragraph):
            if pending_heading:
                units.append(pending_heading)
            pending_heading = paragraph
            continue

        if pending_heading:
            units.append(f"{pending_heading}\n\n{paragraph}")
            pending_heading = None
        else:
            units.append(paragraph)

    if pending_heading:
        units.append(pending_heading)

    return _pack_units(units, target, maximum)
