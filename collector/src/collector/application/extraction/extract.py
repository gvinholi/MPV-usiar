"""Extrai texto de um artefato já adquirido. Sem triagem e sem OCR."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID, uuid4
from zipfile import ZipFile

from collector.application.acquisition.filetype import detect_file_type
from collector.application.acquisition.policy import DocumentAcquisitionPolicy
from collector.application.acquisition.ports import ArtifactStorage
from collector.application.acquisition.zipinspect import inspect_zip
from collector.application.extraction.classify import classify_extraction, page_has_text
from collector.application.extraction.errors import ExtractionError
from collector.application.extraction.integrity import verify_artifact_blob
from collector.application.extraction.members import materialize_zip_member
from collector.application.extraction.policy import TextExtractionPolicy
from collector.application.extraction.ports import PdfTextExtractor
from collector.application.extraction.reasons import ExtractionReason
from collector.application.extraction.results import (
    ArtifactTextExtractionResult,
    ExtractionIssue,
    ExtractionMetrics,
    SourceExtraction,
)
from collector.domain.artifact import Artifact, FileType
from collector.domain.text import ExtractionStatus, TextPage, TextSource
from collector.domain.timestamps import utc_now

Clock = Callable[[], datetime]
IdFactory = Callable[[], UUID]


class ExtractArtifactText:
    def __init__(
        self,
        storage: ArtifactStorage,
        extractor: PdfTextExtractor,
        *,
        policy: TextExtractionPolicy | None = None,
        archive_policy: DocumentAcquisitionPolicy | None = None,
        clock: Clock = utc_now,
        new_id: IdFactory = uuid4,
    ) -> None:
        self._storage = storage
        self._extractor = extractor
        self._policy = policy or TextExtractionPolicy()
        self._archive_policy = archive_policy or DocumentAcquisitionPolicy()
        self._clock = clock
        self._new_id = new_id

    def extract(self, artifact: Artifact) -> ArtifactTextExtractionResult:
        started = self._clock()
        issues: list[ExtractionIssue] = []
        sources: list[SourceExtraction] = []
        try:
            verify_artifact_blob(self._storage, artifact)
        except ExtractionError as exc:
            finished = self._clock()
            issue = ExtractionIssue(reason=exc.reason, message=str(exc))
            return _result(
                artifact,
                complete=False,
                sources=(),
                errors=(issue,),
                started=started,
                finished=finished,
                extractor=self._extractor,
            )

        try:
            header, blob = _read_header_and_reopen(self._storage, artifact)
        except ExtractionError as exc:
            issue = ExtractionIssue(reason=exc.reason, message=str(exc))
            return _result(
                artifact,
                complete=False,
                sources=(),
                errors=(issue,),
                started=started,
                finished=self._clock(),
                extractor=self._extractor,
            )

        detected = detect_file_type(header)
        if detected is FileType.PDF:
            sources.append(self._extract_direct_pdf(artifact, blob))
        elif detected is FileType.ZIP:
            sources.extend(self._extract_zip(artifact, blob, issues))
        else:
            issues.append(
                ExtractionIssue(
                    reason=ExtractionReason.UNSUPPORTED_FORMAT,
                    message="formato de artefato não suportado para extração",
                )
            )
            sources.append(
                _unsupported_source(
                    artifact,
                    f"artifact:{artifact.sha256}",
                    artifact.sha256,
                    artifact.size_bytes,
                    self._new_id(),
                )
            )

        finished = self._clock()
        complete = _is_complete(sources, issues)
        return _result(
            artifact,
            complete=complete,
            sources=tuple(sources),
            errors=tuple(issues),
            started=started,
            finished=finished,
            extractor=self._extractor,
        )

    def _extract_direct_pdf(self, artifact: Artifact, blob) -> SourceExtraction:
        with blob:
            return self._extract_pdf_stream(
                artifact,
                stream=blob,
                source_path=f"artifact:{artifact.sha256}",
                sha256=artifact.sha256,
                size_bytes=artifact.size_bytes,
                archive_entry_id=None,
            )

    def _extract_zip(
        self,
        artifact: Artifact,
        blob,
        issues: list[ExtractionIssue],
    ) -> list[SourceExtraction]:
        sources: list[SourceExtraction] = []
        with blob:
            summary = inspect_zip(blob, self._archive_policy)
            if not summary.safe:
                issues.append(
                    ExtractionIssue(
                        reason=ExtractionReason.UNSAFE_ARCHIVE,
                        message="ZIP inseguro não é extraído",
                    )
                )
                return sources
            blob.seek(0)
            with ZipFile(blob) as archive:
                pdfs_seen = 0
                for info in archive.infolist():
                    if info.is_dir():
                        continue
                    try:
                        temp, digest, size = materialize_zip_member(
                            archive, info, self._storage, self._policy
                        )
                    except ExtractionError as exc:
                        issues.append(
                            ExtractionIssue(
                                reason=exc.reason,
                                message=str(exc),
                                source_path=info.filename,
                            )
                        )
                        continue
                    try:
                        with temp.open_read() as member:
                            header = member.read(8)
                            member.seek(0)
                            kind = detect_file_type(header)
                            if kind is not FileType.PDF:
                                sources.append(
                                    _unsupported_source(
                                        artifact,
                                        info.filename,
                                        digest,
                                        size,
                                        self._new_id(),
                                    )
                                )
                                issues.append(
                                    ExtractionIssue(
                                        reason=ExtractionReason.UNSUPPORTED_FORMAT,
                                        message="member sem texto extraível",
                                        source_path=info.filename,
                                    )
                                )
                                continue
                            pdfs_seen += 1
                            if pdfs_seen > self._policy.max_pdfs_per_artifact:
                                issues.append(
                                    ExtractionIssue(
                                        reason=ExtractionReason.MEMBER_LIMIT_EXCEEDED,
                                        message="número de PDFs excede o limite do artefato",
                                        source_path=info.filename,
                                    )
                                )
                                sources.append(
                                    _failed_source(
                                        artifact,
                                        info.filename,
                                        digest,
                                        size,
                                        ExtractionReason.MEMBER_LIMIT_EXCEEDED,
                                        "número de PDFs excede o limite do artefato",
                                        self._new_id(),
                                    )
                                )
                                continue
                            sources.append(
                                self._extract_pdf_stream(
                                    artifact,
                                    stream=member,
                                    source_path=info.filename,
                                    sha256=digest,
                                    size_bytes=size,
                                    archive_entry_id=None,
                                )
                            )
                    finally:
                        temp.discard()
        return sources

    def _extract_pdf_stream(
        self,
        artifact: Artifact,
        *,
        stream,
        source_path: str,
        sha256: str,
        size_bytes: int,
        archive_entry_id: UUID | None,
    ) -> SourceExtraction:
        header = stream.read(8)
        stream.seek(0)
        if detect_file_type(header) is not FileType.PDF:
            return _unsupported_source(
                artifact, source_path, sha256, size_bytes, self._new_id()
            )
        source = TextSource(
            id=self._new_id(),
            artifact_id=artifact.id,
            source_path=source_path,
            sha256=sha256,
            size_bytes=size_bytes,
            detected_type=FileType.PDF,
            archive_entry_id=archive_entry_id,
        )
        try:
            pages = self._extractor.extract_pages(stream)
        except ExtractionError as exc:
            return SourceExtraction(
                source=source,
                status=ExtractionStatus.FAILED,
                pages=(),
                page_count=0,
                pages_with_text=0,
                character_count=0,
                likely_scanned=False,
                error=ExtractionIssue(
                    reason=exc.reason, message=str(exc), source_path=source_path
                ),
            )
        limited, limit_error = _apply_limits(pages, self._policy)
        status, scanned = classify_extraction(limited, self._policy)
        if limit_error is not None:
            status = ExtractionStatus.FAILED
            scanned = False
        return SourceExtraction(
            source=source,
            status=status,
            pages=limited,
            page_count=len(limited),
            pages_with_text=sum(1 for page in limited if page_has_text(page)),
            character_count=sum(page.char_count for page in limited),
            likely_scanned=scanned,
            error=limit_error,
        )


def _is_complete(
    sources: list[SourceExtraction], issues: list[ExtractionIssue]
) -> bool:
    if any(
        issue.reason
        in {
            ExtractionReason.UNSAFE_ARCHIVE,
            ExtractionReason.ARTIFACT_INTEGRITY_MISMATCH,
            ExtractionReason.ARTIFACT_NOT_FOUND,
            ExtractionReason.UNSUPPORTED_FORMAT,
        }
        and issue.source_path is None
        for issue in issues
    ):
        return False
    if not sources:
        return False
    return all(
        item.status
        in {
            ExtractionStatus.DIGITAL_TEXT,
            ExtractionStatus.EMPTY_TEXT,
            ExtractionStatus.LIKELY_SCANNED,
        }
        for item in sources
    )


def _apply_limits(
    pages: tuple[TextPage, ...], policy: TextExtractionPolicy
) -> tuple[tuple[TextPage, ...], ExtractionIssue | None]:
    if len(pages) > policy.max_pages_per_pdf:
        kept = pages[: policy.max_pages_per_pdf]
        return kept, ExtractionIssue(
            reason=ExtractionReason.PDF_PAGE_LIMIT_EXCEEDED,
            message="PDF excede o limite de páginas",
        )
    total = 0
    kept: list[TextPage] = []
    for page in pages:
        if total + page.char_count > policy.max_chars_per_pdf:
            return tuple(kept), ExtractionIssue(
                reason=ExtractionReason.TEXT_CHARACTER_LIMIT_EXCEEDED,
                message="PDF excede o limite de caracteres",
            )
        kept.append(page)
        total += page.char_count
    return tuple(kept), None


def _unsupported_source(
    artifact: Artifact,
    source_path: str,
    sha256: str,
    size_bytes: int,
    source_id: UUID,
) -> SourceExtraction:
    source = TextSource(
        id=source_id,
        artifact_id=artifact.id,
        source_path=source_path,
        sha256=sha256 if _looks_sha(sha256) else ("0" * 64),
        size_bytes=size_bytes,
        detected_type=FileType.UNKNOWN,
    )
    return SourceExtraction(
        source=source,
        status=ExtractionStatus.UNSUPPORTED,
        pages=(),
        page_count=0,
        pages_with_text=0,
        character_count=0,
        likely_scanned=False,
        error=ExtractionIssue(
            reason=ExtractionReason.UNSUPPORTED_FORMAT,
            message="formato não suportado",
            source_path=source_path,
        ),
    )


def _failed_source(
    artifact: Artifact,
    source_path: str,
    sha256: str,
    size_bytes: int,
    reason: ExtractionReason,
    message: str,
    source_id: UUID,
) -> SourceExtraction:
    return SourceExtraction(
        source=TextSource(
            id=source_id,
            artifact_id=artifact.id,
            source_path=source_path,
            sha256=sha256,
            size_bytes=size_bytes,
            detected_type=FileType.PDF,
        ),
        status=ExtractionStatus.FAILED,
        pages=(),
        page_count=0,
        pages_with_text=0,
        character_count=0,
        likely_scanned=False,
        error=ExtractionIssue(reason=reason, message=message, source_path=source_path),
    )


def _looks_sha(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _read_header_and_reopen(storage: ArtifactStorage, artifact: Artifact):
    try:
        stream = storage.open(artifact.storage_key)
        header = stream.read(8)
        if hasattr(stream, "seek"):
            stream.seek(0)
            return header, stream
        stream.close()
        return header, storage.open(artifact.storage_key)
    except OSError as exc:
        raise ExtractionError(
            "falha ao ler artefato do storage",
            reason=ExtractionReason.STORAGE_READ_ERROR,
        ) from exc


def _metrics(sources: list[SourceExtraction]) -> ExtractionMetrics:
    extracted = [
        item
        for item in sources
        if item.status
        in {
            ExtractionStatus.DIGITAL_TEXT,
            ExtractionStatus.EMPTY_TEXT,
            ExtractionStatus.LIKELY_SCANNED,
        }
    ]
    failed = [item for item in sources if item.status is ExtractionStatus.FAILED]
    unsupported = [item for item in sources if item.status is ExtractionStatus.UNSUPPORTED]
    pages_total = sum(item.page_count for item in sources)
    pages_with_text = sum(item.pages_with_text for item in sources)
    return ExtractionMetrics(
        files_considered=len(sources),
        files_extracted=len(extracted),
        files_failed=len(failed),
        files_unsupported=len(unsupported),
        pages_total=pages_total,
        pages_with_text=pages_with_text,
        pages_without_text=pages_total - pages_with_text,
        characters_extracted=sum(item.character_count for item in extracted),
        likely_scanned_files=sum(1 for item in sources if item.likely_scanned),
    )


def _result(
    artifact: Artifact,
    *,
    complete: bool,
    sources: tuple[SourceExtraction, ...],
    errors: tuple[ExtractionIssue, ...],
    started: datetime,
    finished: datetime,
    extractor: PdfTextExtractor,
) -> ArtifactTextExtractionResult:
    return ArtifactTextExtractionResult(
        artifact_id=artifact.id,
        artifact_sha256=artifact.sha256,
        complete=complete,
        sources=sources,
        metrics=_metrics(list(sources)),
        errors=errors,
        started_at=started,
        finished_at=finished,
        extractor_name=extractor.name,
        extractor_version=extractor.version,
    )
