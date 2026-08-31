"""MNP V1 -- deterministic Resume Parser (`MNP_RESUME_PARSER_V1`). No LLM
tokens anywhere in this package (Founder Decision #4). Pipeline: upload
-> validate -> text extraction -> section detection -> entity extraction
-> normalization -> evidence creation -> Career Card update
(`parser.py::parse_and_apply_resume`)."""
