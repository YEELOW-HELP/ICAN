"""Official ESCO <-> O*NET crosswalk loader (brief §10).

Source: the crosswalk file published by the National Center for O*NET
Development at https://www.onetcenter.org/crosswalks/esco/ , built by the
EU + O*NET with AI techniques and human validation (see the O*NET-ESCO
Technical Report).

This flat file gives ESCO/ISCO code <-> O*NET-SOC 2019 code pairs. It does
NOT carry a per-pair relation semantics (exact / close / broad / narrow) —
that lives in the ESCO-portal RDF version. So every row is loaded with
`mapping_relation = 'unspecified'`; nothing here is ever silently promoted
to 'exact'.
"""
