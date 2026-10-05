"""Materializa um member de ZIP sem extractall."""

from __future__ import annotations

import hashlib
from zipfile import ZipFile, ZipInfo

from collector.application.acquisition.ports import ArtifactStorage, TempBlob
from collector.application.acquisition.zipinspect import classify_archive_path
from collector.application.extraction.errors import ExtractionError
from collector.application.extraction.policy import TextExtractionPolicy
from collector.application.extraction.reasons import ExtractionReason


def materialize_zip_member(
    archive: ZipFile,
    info: ZipInfo,
    storage: ArtifactStorage,
    policy: TextExtractionPolicy,
) -> tuple[TempBlob, str, int]:
    unsafe, reason = classify_archive_path(info.filename)
    if unsafe:
        raise ExtractionError(
            reason or "caminho de member inseguro",
            reason=ExtractionReason.UNSAFE_ARCHIVE,
        )
    if info.file_size > policy.max_member_bytes:
        raise ExtractionError(
            "member excede o limite de bytes",
            reason=ExtractionReason.MEMBER_LIMIT_EXCEEDED,
        )
    temp = storage.open_temp()
    hasher = hashlib.sha256()
    size = 0
    try:
        with archive.open(info, "r") as member:
            while True:
                chunk = member.read(64 * 1024)
                if not chunk:
                    break
                if size + len(chunk) > policy.max_member_bytes:
                    raise ExtractionError(
                        "bytes materializados excedem o limite do member",
                        reason=ExtractionReason.MEMBER_LIMIT_EXCEEDED,
                    )
                temp.write(chunk)
                hasher.update(chunk)
                size += len(chunk)
    except ExtractionError:
        temp.discard()
        raise
    except Exception as exc:
        temp.discard()
        raise ExtractionError(
            "falha ao materializar member do ZIP",
            reason=ExtractionReason.EXTRACTION_ERROR,
        ) from exc
    return temp, hasher.hexdigest(), size
