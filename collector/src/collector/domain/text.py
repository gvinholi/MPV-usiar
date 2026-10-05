"""Fonte textual de um artefato. Não é identidade oficial da contratação."""

from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from collector.domain.artifact import FileType


class ExtractionStatus(Enum):
    DIGITAL_TEXT = "DIGITAL_TEXT"
    EMPTY_TEXT = "EMPTY_TEXT"
    LIKELY_SCANNED = "LIKELY_SCANNED"
    FAILED = "FAILED"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True)
class TextSource:
    id: UUID
    artifact_id: UUID
    source_path: str
    sha256: str
    size_bytes: int
    detected_type: FileType
    archive_entry_id: UUID | None = None

    def __post_init__(self) -> None:
        digest = self.sha256.strip().lower()
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError("sha256 do member deve ter 64 dígitos hexadecimais")
        if not self.source_path.strip():
            raise ValueError("source_path é obrigatório")
        if self.size_bytes < 0:
            raise ValueError("size_bytes não pode ser negativo")
        object.__setattr__(self, "sha256", digest)
        object.__setattr__(self, "source_path", self.source_path.strip())


@dataclass(frozen=True)
class TextPage:
    page_number: int
    text: str
    char_count: int

    def __post_init__(self) -> None:
        if self.page_number < 1:
            raise ValueError("page_number começa em 1")
        if self.char_count < 0:
            raise ValueError("char_count não pode ser negativo")
