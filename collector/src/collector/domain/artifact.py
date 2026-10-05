"""Artefato técnico de um documento. Não é versão oficial da fonte."""

from dataclasses import dataclass
from enum import Enum
from uuid import UUID

HASH_ALGORITHM_SHA256 = "sha256"


class FileType(Enum):
    PDF = "PDF"
    ZIP = "ZIP"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Artifact:
    """Identidade técnica do conteúdo observado, não identidade oficial PNCP."""

    id: UUID
    sha256: str
    size_bytes: int
    detected_type: FileType
    storage_key: str
    hash_algorithm: str = HASH_ALGORITHM_SHA256

    def __post_init__(self) -> None:
        digest = self.sha256.strip().lower()
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError("sha256 deve ter 64 dígitos hexadecimais")
        if self.size_bytes < 0:
            raise ValueError("size_bytes não pode ser negativo")
        if not self.storage_key.strip():
            raise ValueError("storage_key é obrigatório")
        if self.hash_algorithm != HASH_ALGORITHM_SHA256:
            raise ValueError("único algoritmo suportado é sha256")
        object.__setattr__(self, "sha256", digest)


@dataclass(frozen=True)
class ArchiveEntry:
    original_path: str
    compressed_size: int | None = None
    uncompressed_size: int | None = None
    is_directory: bool = False
    extension: str | None = None
    is_encrypted: bool = False
    is_symlink: bool = False
    has_unsafe_path: bool = False
    unsafe_path_reason: str | None = None
