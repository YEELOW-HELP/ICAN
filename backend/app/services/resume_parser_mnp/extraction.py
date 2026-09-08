"""Text extraction, MNP_RESUME_PARSER_V1 "Baseline formats": PDF (text
layer), DOCX, TXT. Delegates PDF/DOCX to the existing, already-tested
`app.services.documents.extract_text` (Stage 1's CV pipeline) rather than
duplicating that logic -- but does NOT modify that shared module, since
it has its own test explicitly asserting `.txt` is unsupported
(`tests/test_documents.py::test_extract_text_rejects_unsupported_extension`,
a real, deliberate constraint of that other, still-active flow). TXT
support is added here, one layer up, instead."""

from __future__ import annotations

from app.services import documents as _shared_documents


class UnsupportedDocumentError(Exception):
    pass


class NoTextLayerError(Exception):
    """PDF/DOCX opened fine but contains no extractable text -- almost
    always a scanned/image-only document. MNP_RESUME_PARSER_V1: "Image-
    only/scanned documents return OCR_REQUIRED until OCR module exists"."""


class CorruptFileError(Exception):
    """The file could not be opened/parsed at all (not merely empty)."""


SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".txt")


def extract_text(file_bytes: bytes, filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".txt"):
        text = _extract_txt(file_bytes)
    elif lower.endswith((".pdf", ".docx")):
        try:
            text = _shared_documents.extract_text(file_bytes, filename)
        except _shared_documents.UnsupportedDocumentError as exc:
            raise UnsupportedDocumentError(str(exc)) from exc
        except Exception as exc:  # pypdf/python-docx raise their own exception types on truly corrupt input
            raise CorruptFileError(str(exc)) from exc
    else:
        raise UnsupportedDocumentError(f"Unsupported file type: {filename}")

    if not text.strip():
        raise NoTextLayerError(f"{filename} produced no extractable text")
    return text


def _extract_txt(file_bytes: bytes) -> str:
    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return file_bytes.decode("cp1251", errors="replace")  # common for legacy UA/RU-locale text files
