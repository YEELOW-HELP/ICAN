# MNP RESUME PARSER V1

## Goal
Convert CV content into structured Career Capital without LLM dependency.

## Flow
`upload → validate → text extraction → section detection → entity extraction → normalization → evidence creation → Career Card update`.

## Baseline formats
PDF with text layer, DOCX, TXT. Adapter architecture for additional text-extractable formats. Image-only/scanned documents return `OCR_REQUIRED` until OCR module exists.

## Extract
- contacts only where needed for account/profile;
- job titles, employers, dates;
- responsibilities and achievements;
- education;
- explicit skills/tools;
- languages;
- credentials/certifications;
- management scope/team size where explicit.

## Deterministic normalization
- regex/date parsing;
- section dictionaries;
- UK/RU/EN title aliases;
- MNP Career aliases;
- MNP Skill aliases;
- ESCO/O*NET mappings only through approved mapping tables.

## Evidence
Explicit CV phrase = CLAIMED.
Rule-derived skill = INFERRED.
Parser never marks VERIFIED by itself.

## Unknown
No mention means UNKNOWN, not ABSENT.

## Output
CareerCard patch + evidence records + unmapped phrases + parser diagnostics.

## Error states
UNSUPPORTED_FORMAT, CORRUPT_FILE, NO_TEXT_LAYER, EMPTY_DOCUMENT, PARSE_PARTIAL.

## Security
File type validation, size limits, malware-safe storage boundary, no execution/macros, access control, deletion support.

## Acceptance
Same fixture CV produces stable normalized output under same parser/taxonomy versions.
