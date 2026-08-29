# MNP CAREER KB ETL V1

## Sources
- ESCO: occupations, skills/competences, relations, labels, ISCO mappings.
- O*NET: skills, knowledge, tasks, work activities/context/styles, interests, education/experience, related occupations, technology skills.
- Ukrainian classifier/legal sources where relevant.
- Approved Ukrainian market sources for aliases and observed requirements.
- Lightcast: excluded.

## Pipeline
`download/import → raw staging → source versioning → normalize → map to MNP IDs → dedupe → UA lexical enrichment → editorial validation → publish`.

## Rules
- Never overwrite raw source data.
- Mapping confidence stored.
- Conflicts preserved and reviewed.
- External IDs never become MNP primary keys.
- License/attribution metadata stored with imported datasets.
- Production KB generated from reproducible transformation scripts.

## Initial scope
Quality coverage for 50 careers and all skills/knowledge required by them.
