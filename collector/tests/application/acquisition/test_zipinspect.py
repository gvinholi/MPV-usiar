"""Inspeção de ZIP sem extração."""

import io

from zipfile import ZipInfo

from collector.application import AcquisitionReason, DocumentAcquisitionPolicy, inspect_zip
from collector.application.acquisition.zipinspect import _summarize, classify_archive_path
from tests.application.acquisition.zip_fixtures import symlink_zip, zip_bytes


def _inspect(payload: bytes, **kwargs) -> object:
    policy = DocumentAcquisitionPolicy(**kwargs) if kwargs else DocumentAcquisitionPolicy()
    return inspect_zip(io.BytesIO(payload), policy)


def test_normal_zip_is_safe() -> None:
    summary = _inspect(zip_bytes(("edital.pdf", b"%PDF-1.4"), ("anexo/a.txt", b"ok")))
    assert summary.safe is True
    assert summary.entry_count == 2
    assert {entry.original_path for entry in summary.entries} == {
        "edital.pdf",
        "anexo/a.txt",
    }


def test_directory_entry() -> None:
    summary = _inspect(zip_bytes(("pasta/", b"")))
    assert summary.entries[0].is_directory is True
    assert summary.safe is True


def test_path_traversal() -> None:
    summary = _inspect(zip_bytes(("../../etc/passwd", b"x")))
    assert summary.safe is False
    assert AcquisitionReason.ARCHIVE_PATH_TRAVERSAL in summary.flags
    assert summary.entries[0].has_unsafe_path is True


def test_absolute_unix_and_windows_paths() -> None:
    assert classify_archive_path("/etc/passwd")[0] is True
    assert classify_archive_path("C:\\Windows\\win.ini")[0] is True
    assert classify_archive_path("edital.pdf")[0] is False


def test_too_many_entries() -> None:
    payload = zip_bytes(*[(f"{index}.txt", b"x") for index in range(4)])
    summary = _inspect(payload, max_archive_entries=3)
    assert AcquisitionReason.ARCHIVE_LIMIT_EXCEEDED in summary.flags


def test_uncompressed_size_limit() -> None:
    summary = _inspect(zip_bytes(("big.txt", b"0123456789")), max_entry_uncompressed_bytes=5)
    assert AcquisitionReason.ARCHIVE_LIMIT_EXCEEDED in summary.flags


def test_ratio_limit_with_zeros() -> None:
    summary = _inspect(
        zip_bytes(("zeros.bin", b"\x00" * 10_000)),
        max_compression_ratio=2.0,
    )
    assert AcquisitionReason.ARCHIVE_LIMIT_EXCEEDED in summary.flags


def test_encrypted_entry() -> None:
    info = ZipInfo("secret.pdf")
    info.flag_bits = 0x1
    summary = _summarize([info], DocumentAcquisitionPolicy())
    assert summary.entries[0].is_encrypted is True
    assert AcquisitionReason.ENCRYPTED_ARCHIVE_ENTRY in summary.flags


def test_symlink_entry() -> None:
    summary = _inspect(symlink_zip())
    assert summary.entries[0].is_symlink is True
    assert AcquisitionReason.ARCHIVE_SYMLINK in summary.flags


def test_invalid_zip() -> None:
    summary = _inspect(b"isto nao e zip")
    assert summary.safe is False
    assert summary.flags == (AcquisitionReason.INVALID_ZIP,)
