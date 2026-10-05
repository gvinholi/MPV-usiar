"""Assinaturas PDF/ZIP. Sem extensão e sem Content-Type."""

from collector.application import detect_file_type
from collector.domain import FileType
from tests.application.acquisition.zip_fixtures import PDF_BYTES, UNKNOWN_BYTES, zip_bytes


def test_pdf_magic() -> None:
    assert detect_file_type(PDF_BYTES) is FileType.PDF


def test_zip_magic() -> None:
    assert detect_file_type(zip_bytes(("a.txt", b"a"))) is FileType.ZIP


def test_unknown() -> None:
    assert detect_file_type(UNKNOWN_BYTES) is FileType.UNKNOWN
    assert detect_file_type(b"") is FileType.UNKNOWN
