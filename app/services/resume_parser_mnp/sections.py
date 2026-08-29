"""Section detection, MNP_RESUME_PARSER_V1 "section detection" step."""

from __future__ import annotations

from app.services.resume_parser_mnp.patterns import match_section_header


def split_into_sections(text: str) -> dict[str, list[str]]:
    """Lines before the first recognized header land under "header"
    (contact info, name, etc. -- not parsed further in BLOCK B)."""

    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for line in text.splitlines():
        header = match_section_header(line)
        if header:
            current = header
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return sections
