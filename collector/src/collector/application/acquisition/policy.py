"""Limites centralizados da aquisição. Sem números mágicos nas bordas."""

from dataclasses import dataclass

# 50 MiB: os ZIPs observados no piloto tinham ~1,4 MiB. O teto cobre
# editais/anexos típicos sem aceitar downloads de centenas de MiB.
DEFAULT_MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024
# 60s: o GET real do ZIP de ~1,4 MiB no PNCP completou em ~8s, mas a
# primeira tentativa com 30s falhou por timeout em conexão fria.
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_REDIRECTS = 5
DEFAULT_MAX_ARCHIVE_ENTRIES = 500
DEFAULT_MAX_ENTRY_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
DEFAULT_MAX_TOTAL_UNCOMPRESSED_BYTES = 250 * 1024 * 1024
DEFAULT_MAX_COMPRESSION_RATIO = 100.0


@dataclass(frozen=True)
class DocumentAcquisitionPolicy:
    max_download_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_redirects: int = DEFAULT_MAX_REDIRECTS
    max_archive_entries: int = DEFAULT_MAX_ARCHIVE_ENTRIES
    max_entry_uncompressed_bytes: int = DEFAULT_MAX_ENTRY_UNCOMPRESSED_BYTES
    max_total_uncompressed_bytes: int = DEFAULT_MAX_TOTAL_UNCOMPRESSED_BYTES
    max_compression_ratio: float = DEFAULT_MAX_COMPRESSION_RATIO

    def __post_init__(self) -> None:
        if self.max_download_bytes < 1:
            raise ValueError("max_download_bytes deve ser >= 1")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds deve ser > 0")
        if self.max_redirects < 0:
            raise ValueError("max_redirects não pode ser negativo")
        if self.max_archive_entries < 1:
            raise ValueError("max_archive_entries deve ser >= 1")
        if self.max_entry_uncompressed_bytes < 1:
            raise ValueError("max_entry_uncompressed_bytes deve ser >= 1")
        if self.max_total_uncompressed_bytes < 1:
            raise ValueError("max_total_uncompressed_bytes deve ser >= 1")
        if self.max_compression_ratio < 1:
            raise ValueError("max_compression_ratio deve ser >= 1")
