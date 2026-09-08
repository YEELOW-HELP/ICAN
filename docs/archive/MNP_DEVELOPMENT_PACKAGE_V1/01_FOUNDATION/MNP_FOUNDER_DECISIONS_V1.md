# MNP FOUNDER DECISIONS V1

Status: APPROVED baseline.

1. Adult-first main product; teen page/vertical is secondary.
2. Resume-first, but CV is not mandatory.
3. Without CV, user builds Career Card via structured adaptive questionnaire.
4. BASIC core uses no LLM tokens.
5. Supported baseline CV formats: text PDF, DOCX, TXT; architecture should accept additional extractable formats. OCR/scans later.
6. No mandatory confirmation screen after parsing; result is immediate.
7. Career Card is a long-lived master profile; calculations use versioned snapshots.
8. User may edit Career Card later; edits are CLAIMED evidence unless independently verified.
9. Current income is optional.
10. Skill proficiency V1 has 3 internal levels: BASIC / WORKING / STRONG.
11. Career Knowledge Base is a separate managed module.
12. Initial universe: 50 ACTIVE careers.
13. ADMIN/EDITOR may add/update/archive careers with audit history.
14. Market layer may refresh monthly; core occupational profile changes less frequently.
15. Numeric Match Score is internal only in V1.
16. MNP owns Career and Skill identifiers.
17. ESCO/O*NET can be used as open knowledge/mapping sources.
18. Lightcast is not used in V1.
19. Career Profile uses UK + EN canonical names.
20. Junior/Middle/Senior are career levels/variants, not separate careers by default.
21. Career aliases do not automatically create new careers.
22. RIASEC may be stored as a secondary signal, not adult matching core.
23. O*NET abilities may be stored, but are not strong ranking factors before validation.
24. Structured Career Profile is required; long SEO article is not required for launch.
25. Career may be ACTIVE with limited market data only when clearly marked MARKET_DATA_LIMITED.
26. Initial 50 careers are selected using market demand + income opportunity + transferability + transition feasibility + relevance, not Work.ua popularity alone.
27. `UNKNOWN` is a first-class state; absence from CV does not mean absence of skill.
28. Hard BLOCKED status requires authoritative/high-confidence evidence.
29. High fit + low confidence does not enter Featured TOP-3 by default.
30. Optional clarification may be offered after result, never block initial result.
