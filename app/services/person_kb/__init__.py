"""PERSON KB BASE V1 service layer.

ONE canonical Person KB (`MnpPerson` + fact tables). All three entry
flows -- user manual profile, user CV upload+review, admin manual --
write through here. Never fabricates proficiency / evidence; a CV
candidate stays `SYSTEM_DETECTED` until a human confirms it.
"""
