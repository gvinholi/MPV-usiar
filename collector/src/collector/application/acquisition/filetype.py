"""Identificação por assinatura. Não usa extensão, título nem Content-Type."""

from collector.domain.artifact import FileType

_PDF_MAGIC = b"%PDF-"
_ZIP_LOCAL = b"PK\x03\x04"
_ZIP_EMPTY = b"PK\x05\x06"
_ZIP_SPAN = b"PK\x06\x06"
_ZIP_SPANNED = b"PK\x07\x08"


def detect_file_type(header: bytes) -> FileType:
    if header.startswith(_PDF_MAGIC):
        return FileType.PDF
    if header.startswith((_ZIP_LOCAL, _ZIP_EMPTY, _ZIP_SPAN, _ZIP_SPANNED)):
        return FileType.ZIP
    return FileType.UNKNOWN
