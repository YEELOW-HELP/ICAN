"""Pure, deterministic entity extraction over already-section-split CV
text (MNP_RESUME_PARSER_V1 "entity extraction" + "normalization" steps).
No SQLAlchemy import here -- mirrors this repo's "matching engine is
pure/deterministic where possible" architecture principle
(`MNP_SYSTEM_ARCHITECTURE_V1` "Boundaries"), applied to the parser too:
this module is unit-testable with plain strings in, plain dataclasses
out."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from app.services.resume_parser_mnp.patterns import (
    ACHIEVEMENT_INDICATOR_RE,
    CURRENT_WORDS,
    DATE_RANGE_RE,
    EDUCATION_LEVEL_KEYWORDS,
    GRADUATION_YEAR_RE,
    LANGUAGE_LEVEL_WORDS,
    LANGUAGE_NAMES,
    SKILL_SEPARATORS_RE,
    TEAM_SIZE_RE,
)


@dataclass(frozen=True)
class ParsedExperience:
    raw_job_title: str
    company_name: str | None
    start_date: date | None
    end_date: date | None
    is_current: bool
    responsibilities_raw: str
    achievements: list[str]
    team_size: int | None
    management_scope: bool


@dataclass(frozen=True)
class ParsedEducation:
    raw_line: str
    level: str | None
    graduation_year: int | None


@dataclass(frozen=True)
class ParsedLanguage:
    language_code: str
    overall_level: str | None
    raw_line: str


@dataclass(frozen=True)
class ParsedCredential:
    name: str


@dataclass(frozen=True)
class ParsedResume:
    experiences: list[ParsedExperience] = field(default_factory=list)
    educations: list[ParsedEducation] = field(default_factory=list)
    raw_skill_phrases: list[str] = field(default_factory=list)
    languages: list[ParsedLanguage] = field(default_factory=list)
    credentials: list[ParsedCredential] = field(default_factory=list)


def _parse_date_token(token: str) -> date | None:
    token = token.strip()
    if re.fullmatch(r"\d{1,2}[./]\d{4}", token):
        sep = "." if "." in token else "/"
        month_str, year_str = token.split(sep)
        try:
            return date(int(year_str), int(month_str), 1)
        except ValueError:
            return None
    if re.fullmatch(r"\d{4}", token):
        return date(int(token), 1, 1)
    return None


def _is_current_token(token: str) -> bool:
    return token.strip().lower() in CURRENT_WORDS


def parse_experience_section(lines: list[str]) -> list[ParsedExperience]:
    """Groups lines into blocks anchored on a date-range line (the most
    reliable structural signal across UK/RU/EN CV formats) -- the date
    line's own leftover text (or the next non-empty line, if the date
    line is bare) becomes the job title; everything until the next date
    line is `responsibilities_raw`."""

    blocks: list[list[str]] = []
    current_block: list[str] = []
    for line in lines:
        if DATE_RANGE_RE.search(line):
            if current_block:
                blocks.append(current_block)
            current_block = [line]
        elif current_block:
            current_block.append(line)
    if current_block:
        blocks.append(current_block)

    experiences: list[ParsedExperience] = []
    for block in blocks:
        header_line = block[0]
        match = DATE_RANGE_RE.search(header_line)
        start_date = _parse_date_token(match.group(1)) if match else None
        is_current = _is_current_token(match.group(2)) if match else False
        end_date = None if is_current else (_parse_date_token(match.group(2)) if match else None)

        title_leftover = DATE_RANGE_RE.sub("", header_line).strip(" -–—|,\t")
        rest_lines = [l.strip() for l in block[1:] if l.strip()]
        if title_leftover:
            raw_job_title = title_leftover
            company_name = None
        elif rest_lines:
            raw_job_title = rest_lines[0]
            rest_lines = rest_lines[1:]
            company_name = None
        else:
            raw_job_title = "Unknown role"
            company_name = None

        # "Title, Company" or "Title — Company" or "Title | Company" on one line.
        for sep in (" — ", " – ", " | ", ", "):
            if sep in raw_job_title:
                parts = raw_job_title.split(sep, 1)
                raw_job_title, company_name = parts[0].strip(), parts[1].strip()
                break

        responsibilities_raw = "\n".join(rest_lines)
        team_match = TEAM_SIZE_RE.search(responsibilities_raw)
        team_size = int(team_match.group(1)) if team_match else None
        achievements = [l for l in rest_lines if ACHIEVEMENT_INDICATOR_RE.search(l)]

        experiences.append(
            ParsedExperience(
                raw_job_title=raw_job_title,
                company_name=company_name,
                start_date=start_date,
                end_date=end_date,
                is_current=is_current,
                responsibilities_raw=responsibilities_raw,
                achievements=achievements,
                team_size=team_size,
                management_scope=team_size is not None,
            )
        )
    return experiences


def parse_education_section(lines: list[str]) -> list[ParsedEducation]:
    educations: list[ParsedEducation] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        year_match = GRADUATION_YEAR_RE.search(stripped)
        graduation_year = int(year_match.group(0)) if year_match else None
        level = None
        lowered = stripped.lower()
        for keyword, canonical in EDUCATION_LEVEL_KEYWORDS.items():
            if keyword in lowered:
                level = canonical
                break
        educations.append(ParsedEducation(raw_line=stripped, level=level, graduation_year=graduation_year))
    return educations


def parse_skills_section(lines: list[str]) -> list[str]:
    joined = "\n".join(lines)
    raw_phrases = [p.strip() for p in SKILL_SEPARATORS_RE.split(joined)]
    seen: set[str] = set()
    result: list[str] = []
    for phrase in raw_phrases:
        if not phrase or len(phrase) > 80:  # a real skill phrase is short; a >80-char "phrase" is a stray sentence
            continue
        key = phrase.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(phrase)
    return result


def parse_languages_section(lines: list[str]) -> list[ParsedLanguage]:
    languages: list[ParsedLanguage] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        matched_code = None
        for code, names in LANGUAGE_NAMES.items():
            if any(name in lowered for name in names):
                matched_code = code
                break
        if matched_code is None:
            continue
        matched_level = None
        for word, canonical in LANGUAGE_LEVEL_WORDS.items():
            if word in lowered:
                matched_level = canonical
                break
        languages.append(ParsedLanguage(language_code=matched_code, overall_level=matched_level, raw_line=stripped))
    return languages


def parse_credentials_section(lines: list[str]) -> list[ParsedCredential]:
    return [ParsedCredential(name=line.strip()) for line in lines if line.strip()]


def parse_resume_sections(sections: dict[str, list[str]]) -> ParsedResume:
    return ParsedResume(
        experiences=parse_experience_section(sections.get("experience", [])),
        educations=parse_education_section(sections.get("education", [])),
        raw_skill_phrases=parse_skills_section(sections.get("skills", [])),
        languages=parse_languages_section(sections.get("languages", [])),
        credentials=parse_credentials_section(sections.get("credentials", [])),
    )
