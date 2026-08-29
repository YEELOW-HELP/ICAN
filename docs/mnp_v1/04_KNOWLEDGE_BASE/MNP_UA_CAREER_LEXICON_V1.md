# MNP UA CAREER LEXICON V1

## Purpose
Normalize Ukrainian labour-market terminology into MNP Careers/Skills.

## Languages
Ukrainian primary; English required for interoperability. Russian aliases may be stored for parsing legacy CVs/market text where legally/product-appropriate, but UI remains Ukrainian-first.

## Sources
MNP editorial vocabulary, Ukrainian classifier, approved job-market terminology, ESCO/O*NET translations/mappings where useful.

## Objects
CareerAlias, SkillAlias, abbreviation, transliteration, common misspelling, market title variant.

## Rule
Alias → canonical entity only after mapping rule/review. Unknown phrases go to review queue and never silently create canonical entities.
