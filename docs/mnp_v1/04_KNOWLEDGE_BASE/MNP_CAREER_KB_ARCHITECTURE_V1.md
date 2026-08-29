# MNP CAREER KNOWLEDGE BASE ARCHITECTURE V1

## Purpose
Managed, versioned source of structured career knowledge independent from matching code.

## Initial publish
50 ACTIVE careers.

## Components
- Career
- Career Family
- Career Alias
- Skill/Knowledge requirements
- Tasks/Activities/Context
- Education/Experience/Credential/Language requirements
- Career Relations
- External Mappings
- Review metadata
- Market snapshot references

## Lifecycle
DRAFT → VALIDATED → ACTIVE → REVIEW_DUE → ACTIVE/ARCHIVED.

## Admin
ADMIN/EDITOR CRUD with audit log. Deletion of referenced canonical careers prohibited; archive/merge instead.

## Monthly operation
Market snapshots can refresh monthly. Career aliases/tools may refresh frequently. Core occupational requirements reviewed quarterly/source-triggered.

## Versioning
Every matching run stores Career KB version and Career Profile versions.
