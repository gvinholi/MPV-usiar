"""Inspeção de ZIP sem extração física dos membros."""

from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath
from typing import BinaryIO
from zipfile import BadZipFile, ZipFile, ZipInfo

from collector.application.acquisition.policy import DocumentAcquisitionPolicy
from collector.application.acquisition.reasons import AcquisitionReason
from collector.application.acquisition.results import ArchiveSummary
from collector.domain.artifact import ArchiveEntry

_UNIX_SYMLINK = 0xA000
_ZIP_ENCRYPTED = 0x1


def inspect_zip(stream: BinaryIO, policy: DocumentAcquisitionPolicy) -> ArchiveSummary:
    try:
        archive = ZipFile(stream)
    except BadZipFile:
        return ArchiveSummary(
            entry_count=0,
            total_compressed_bytes=0,
            total_uncompressed_bytes=0,
            safe=False,
            flags=(AcquisitionReason.INVALID_ZIP,),
            entries=(),
        )

    with archive:
        infos = archive.infolist()
        return _summarize(infos, policy)


def _summarize(infos: list[ZipInfo], policy: DocumentAcquisitionPolicy) -> ArchiveSummary:
    flags: list[AcquisitionReason] = []
    entries: list[ArchiveEntry] = []
    total_compressed = 0
    total_uncompressed = 0

    if len(infos) > policy.max_archive_entries:
        flags.append(AcquisitionReason.ARCHIVE_LIMIT_EXCEEDED)

    for info in infos:
        compressed = max(info.compress_size, 0)
        uncompressed = max(info.file_size, 0)
        total_compressed += compressed
        total_uncompressed += uncompressed
        unsafe, unsafe_reason = classify_archive_path(info.filename)
        encrypted = bool(info.flag_bits & _ZIP_ENCRYPTED)
        symlink = _is_symlink(info)
        if unsafe:
            flags.append(AcquisitionReason.ARCHIVE_PATH_TRAVERSAL)
        if encrypted:
            flags.append(AcquisitionReason.ENCRYPTED_ARCHIVE_ENTRY)
        if symlink:
            flags.append(AcquisitionReason.ARCHIVE_SYMLINK)
        if uncompressed > policy.max_entry_uncompressed_bytes:
            flags.append(AcquisitionReason.ARCHIVE_LIMIT_EXCEEDED)
        if compressed > 0 and uncompressed / compressed > policy.max_compression_ratio:
            flags.append(AcquisitionReason.ARCHIVE_LIMIT_EXCEEDED)
        entries.append(
            ArchiveEntry(
                original_path=info.filename,
                compressed_size=compressed,
                uncompressed_size=uncompressed,
                is_directory=info.is_dir(),
                extension=_extension(info.filename),
                is_encrypted=encrypted,
                is_symlink=symlink,
                has_unsafe_path=unsafe,
                unsafe_path_reason=unsafe_reason,
            )
        )

    if total_uncompressed > policy.max_total_uncompressed_bytes:
        flags.append(AcquisitionReason.ARCHIVE_LIMIT_EXCEEDED)

    unique_flags = tuple(dict.fromkeys(flags))
    if unique_flags:
        reasons = list(unique_flags)
        if AcquisitionReason.UNSAFE_ARCHIVE not in reasons:
            reasons.insert(0, AcquisitionReason.UNSAFE_ARCHIVE)
        unique_flags = tuple(reasons)

    return ArchiveSummary(
        entry_count=len(entries),
        total_compressed_bytes=total_compressed,
        total_uncompressed_bytes=total_uncompressed,
        safe=not unique_flags,
        flags=unique_flags,
        entries=tuple(entries),
    )


def classify_archive_path(name: str) -> tuple[bool, str | None]:
    if not name:
        return True, "nome vazio"
    posix = PurePosixPath(name.replace("\\", "/"))
    windows = PureWindowsPath(name)
    if posix.is_absolute() or windows.is_absolute():
        return True, "caminho absoluto"
    if posix.anchor or windows.anchor:
        return True, "caminho absoluto"
    if ".." in posix.parts or ".." in windows.parts:
        return True, "path traversal"
    if name.startswith(("/", "\\")):
        return True, "caminho absoluto"
    if len(name) >= 2 and name[1] == ":" and name[0].isalpha():
        return True, "caminho absoluto Windows"
    return False, None


def _is_symlink(info: ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0xF000
    return mode == _UNIX_SYMLINK


def _extension(name: str) -> str | None:
    stripped = name.rstrip("/\\")
    if "." not in PurePosixPath(stripped.replace("\\", "/")).name:
        return None
    suffix = PurePosixPath(stripped.replace("\\", "/")).suffix
    return suffix.lower() or None
