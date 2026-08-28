# MNP Work.ua Data Use Decision V0.1 — Implementation Gate

**Status:** PROVISIONAL v0.1 — this document is a **hard implementation gate**, not a green light. No automated Work.ua import (scrape, bulk copy, or API pull) may be built or run until this document's open items are resolved by the Founder and, where indicated, by an actual licensing conversation with Work.ua.
**Depends on:** `docs/product/20_MATCHING_V1_FOUNDER_DEFINITION.md` §6A, `MNP_CAREER_KB_V1.md` §B/§F/§H.

Work.ua's Career Guide content (profession descriptions, skill lists, salary/vacancy data) was not licensed to MNP for bulk reuse. This document exists precisely because that fact must not be silently assumed away by an engineering shortcut. **Do not scrape or bulk-import Work.ua content in M0/M1** under any circumstance, regardless of how easy it would be technically.

---

## A. Facts referenceable manually

An MNP curator may read Work.ua's public Career Guide pages and use the *facts* (a profession exists, its general skill requirements, typical education path) as background knowledge to **manually author** MNP's own, independently-worded content. This is the same standard applied to any competitor/reference-site research — facts are not copyrightable, expression is. No automated scraping tool is used for this; it is a human reading a public page and writing original text.

## B. Data storable internally

MNP may store, internally, a reference to which Work.ua page/slug corresponds to which internal `Career.code` (the `CareerExternalMapping` crosswalk row, KB doc §B/§D) — this is metadata about MNP's own data model, not a copy of Work.ua's content, and may be stored regardless of the licensing outcome below.

## C. Data displayable publicly

**Nothing** from Work.ua may be displayed to end users verbatim (descriptions, skill-list wording, salary figures sourced from Work.ua specifically) until the licensing decision (§D) is resolved in MNP's favor, in writing. This includes: profession descriptions, worded skill/requirement lists, and Work.ua-attributed salary/vacancy/trend figures. MNP-authored equivalents (per §A) may be displayed, since they are original content, not a copy.

## D. Data requiring agreement/API/license

The following require an explicit commercial/licensing conversation with Work.ua before any automated or bulk use:
- Bulk import of the ~149-profession catalog structure or wording.
- Any salary/vacancy/trend market data sourced from Work.ua, displayed at any frequency (one-time or recurring).
- Any API integration, if Work.ua offers one, for automated freshness updates.

**This is an explicit, tracked open item** — someone (Founder or a designated business contact) must initiate this conversation; engineering cannot resolve it and must not proceed as if it were resolved.

## E. Data NOT to copy without permission

Explicitly listed to prevent accidental scope creep during implementation: raw HTML/page structure, exact profession description wording, exact skill-list wording and ordering, Work.ua's own categorization/taxonomy structure (MNP may build its *own* categorization informed by having read theirs, but must not copy the structure itself), and any Work.ua-branded UI element or visual design.

---

## Until this gate is resolved

- Career KB V1 (`MNP_CAREER_KB_V1.md`) treats Work.ua strictly as **layer A: reference source**, not an import pipeline.
- The M0–M6 implementation slices (doc 21 §5) do not include a Work.ua importer. M3's O*NET importer proceeds independently, since O*NET carries no equivalent licensing gate (KB doc §C).
- Market-sensitive facts in the initial pilot Career Catalog will be sparse or absent for careers where the only available source was Work.ua, until this gate clears — this is an accepted, explicit V1 limitation, not a bug to silently work around with an unlicensed import.

---

## G. Market data freshness (Open Question)

Even once licensing is resolved, market-sensitive facts (salary, vacancy counts, trend) must never be shown stale. This section specifies the *freshness windows*, independent of the licensing question above (§D governs whether the data may be shown at all; this section governs how long a shown value stays valid).

**Options:**
1. Uniform expiry window for all market-sensitive fact types (e.g. everything expires after 90 days).
2. Fact-type-specific windows (salary ranges expire slower than vacancy counts, which move faster).
3. No fixed window — re-check freshness against the source at render time.

**Pros/Cons:** (1) simple but wrong on the merits — vacancy counts genuinely go stale within weeks, salary bands do not. (2) matches how each metric actually behaves in the labor market, at the cost of one more configuration constant per fact type. (3) most "correct" in principle but requires a live connection to the source at render time, which does not exist for a reference-only source under the current licensing gate (§D) — infeasible until/unless a live API integration is licensed.

**V0.1 RECOMMENDATION:** Option 2, fact-type-specific windows:
- **Salary ranges:** `expires_at = observed_at + 6 months` — salary survey data moves slowly (typically republished quarterly/annually even by primary sources).
- **Vacancy counts:** `expires_at = observed_at + 30 days` — a much more volatile, fast-moving signal.
- **Trend indicator** (growing/stable/declining): `expires_at = observed_at + 6 months` — a slower-moving directional judgment, not a raw count.

**WHY:** Matches each metric's real-world volatility rather than applying one arbitrary constant to all of them; consistent with the existing `CareerFact.is_market_sensitive` + `expires_at` discipline already established in Stage 3A (doc 21 §2.1 KEEP list) — this document only fixes the *window lengths*, not the mechanism.
**PROVISIONAL STATUS:** Provisional — these windows are placeholders pending both the Work.ua licensing outcome (§D) and, if resolved, real observed data-staleness patterns from whatever source ultimately supplies market data (Work.ua under license, or an alternative UA labor-market data source if that licensing conversation does not succeed).
