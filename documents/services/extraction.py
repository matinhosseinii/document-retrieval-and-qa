from pathlib import Path
from zipfile import BadZipFile

from django.core.exceptions import ValidationError
from docx import Document as DocxDocument
from docx.opc.exceptions import PackageNotFoundError
from lxml.etree import XMLSyntaxError


DOCX_EXTENSION_ERROR = "Only DOCX files are supported."
INVALID_DOCX_ERROR = "The uploaded file is not a valid DOCX document."
_EXTRACTED_TEXT_CACHE_ATTRIBUTE = "_document_extracted_text"


def validate_docx_extension(file) -> None:
    """Reject files whose names do not have a .docx extension."""
    filename = getattr(file, "name", "")
    if Path(filename).suffix.lower() != ".docx":
        raise ValidationError(DOCX_EXTENSION_ERROR, code="invalid_extension")


def extract_docx_text(file) -> str:
    """Return all normal paragraph text from a valid DOCX file."""
    try:
        file.seek(0)
        document = DocxDocument(file)
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    except (
        BadZipFile,
        EOFError,
        OSError,
        PackageNotFoundError,
        KeyError,
        ValueError,
        XMLSyntaxError,
    ) as exc:
        raise ValidationError(INVALID_DOCX_ERROR, code="invalid_docx") from exc
    finally:
        try:
            file.seek(0)
        except (AttributeError, OSError, ValueError):
            pass


def validate_and_extract_docx(file) -> str:
    """Validate a DOCX upload, extract it once, and cache the result on the file."""
    validate_docx_extension(file)
    cache_sources = (file, getattr(file, "_file", None))
    for cache_source in cache_sources:
        if cache_source is not None and hasattr(
            cache_source, _EXTRACTED_TEXT_CACHE_ATTRIBUTE
        ):
            return getattr(cache_source, _EXTRACTED_TEXT_CACHE_ATTRIBUTE)

    text = extract_docx_text(file)
    setattr(file, _EXTRACTED_TEXT_CACHE_ATTRIBUTE, text)
    return text


def has_extracted_text_cache(file) -> bool:
    return any(
        cache_source is not None
        and hasattr(cache_source, _EXTRACTED_TEXT_CACHE_ATTRIBUTE)
        for cache_source in (file, getattr(file, "_file", None))
    )


def clear_extracted_text_cache(file) -> None:
    if hasattr(file, _EXTRACTED_TEXT_CACHE_ATTRIBUTE):
        delattr(file, _EXTRACTED_TEXT_CACHE_ATTRIBUTE)
