from __future__ import annotations

import io

import docx
from pypdf import PdfReader


class UnsupportedDocumentError(Exception):
    pass


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Extract plain text from an uploaded CV (PDF or DOCX)."""
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return _extract_pdf(file_bytes)
    if lower.endswith(".docx"):
        return _extract_docx(file_bytes)
    raise UnsupportedDocumentError(f"Unsupported file type: {filename}")


def _extract_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages).strip()


def _extract_docx(file_bytes: bytes) -> str:
    document = docx.Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in document.paragraphs).strip()
