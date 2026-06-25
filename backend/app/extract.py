"""Extract plain text from uploaded reference documents.

The extracted text is what feeds the persona (stored in `Document.content`); the
original bytes are kept in S3. Dispatch is by file extension.

Supported: .txt, .md (decoded directly), .pdf (pypdf), .docx (python-docx),
.doc (best-effort via the `antiword` system binary — see nixpacks.toml).
"""

from __future__ import annotations

import io
import shutil
import subprocess
from pathlib import Path

# Extensions we accept on upload. Mirrors the frontend file picker's `accept`.
SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".doc"}


class UnsupportedFileType(ValueError):
    """The file extension is not one we can extract text from."""


class ExtractionError(RuntimeError):
    """We recognised the type but could not pull any text out of it."""


def _ext(filename: str) -> str:
    return Path(filename).suffix.lower()


def is_supported(filename: str) -> bool:
    return _ext(filename) in SUPPORTED_EXTENSIONS


def extract_text(filename: str, data: bytes) -> str:
    """Return the plain-text content of an uploaded file.

    Raises UnsupportedFileType for unknown extensions and ExtractionError when a
    recognised type yields no usable text.
    """
    ext = _ext(filename)

    if ext in (".txt", ".md"):
        text = data.decode("utf-8", errors="replace")
    elif ext == ".pdf":
        text = _extract_pdf(data)
    elif ext == ".docx":
        text = _extract_docx(data)
    elif ext == ".doc":
        text = _extract_doc(data)
    else:
        raise UnsupportedFileType(
            f"Unsupported file type '{ext or filename}'. "
            "Allowed: .txt, .md, .pdf, .docx, .doc"
        )

    text = text.strip()
    if not text:
        raise ExtractionError(
            f"No readable text could be extracted from '{filename}'."
        )
    return text


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(p.strip() for p in pages if p.strip())


def _extract_docx(data: bytes) -> str:
    import docx  # python-docx

    document = docx.Document(io.BytesIO(data))
    paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def _extract_doc(data: bytes) -> str:
    """Legacy .doc — best-effort via the `antiword` system binary.

    There is no maintained pure-Python parser for the old binary Word format, so
    we shell out to antiword (installed via nixpacks.toml on Railway). If it is
    not present we raise a clear, actionable error.
    """
    antiword = shutil.which("antiword")
    if not antiword:
        raise ExtractionError(
            "Legacy .doc files require the 'antiword' tool, which is not "
            "installed here. Please convert the file to .docx or .pdf and re-upload."
        )
    try:
        result = subprocess.run(
            [antiword, "-"],
            input=data,
            capture_output=True,
            timeout=30,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise ExtractionError(
            "Could not read this .doc file. Please convert it to .docx or .pdf."
        ) from exc
    return result.stdout.decode("utf-8", errors="replace")
