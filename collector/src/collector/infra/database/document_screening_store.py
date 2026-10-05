"""Repositório PostgreSQL da triagem documental. Um processo por vez."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload, sessionmaker

from collector.application.document_screening.results import (
    DocumentPageRef,
    DocumentScreeningCorpus,
    DocumentScreeningEvaluation,
    DocumentSourceRef,
)
from collector.application.persistence.errors import PersistenceError
from collector.application.screening.results import ScreeningEvaluation
from collector.infra.database.document_screening_mapping import document_evaluation_from_row
from collector.infra.database.models import (
    ArtifactRow,
    ArtifactTextSourceRow,
    DocumentArtifactRow,
    DocumentScreeningEvaluationRow,
    DocumentScreeningEvidenceRow,
    ProcessDocumentRow,
    ScreeningEvaluationRow,
    TextExtractionPageRow,
    TextExtractionRow,
)
from collector.infra.database.screening_mapping import evaluation_from_row


class SqlAlchemyDocumentScreeningRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None

    @contextmanager
    def transaction(self):
        session = self._session_factory()
        self._session = session
        try:
            yield
            session.commit()
        except PersistenceError:
            session.rollback()
            raise
        except SQLAlchemyError as exc:
            session.rollback()
            raise PersistenceError("falha inesperada na persistência") from exc
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
            self._session = None

    def load_corpus(self, process_id: UUID) -> DocumentScreeningCorpus:
        return self._load_corpus(process_id, artifact_sha256=None)

    def load_corpus_for_artifact(
        self, process_id: UUID, artifact_sha256: str
    ) -> DocumentScreeningCorpus:
        return self._load_corpus(process_id, artifact_sha256=artifact_sha256.strip().lower())

    def get_evaluation(
        self,
        process_id: UUID,
        profile_id: UUID,
        engine_version: str,
        document_set_fingerprint: str,
    ) -> DocumentScreeningEvaluation | None:
        row = self._require_session().scalar(
            select(DocumentScreeningEvaluationRow)
            .options(
                selectinload(DocumentScreeningEvaluationRow.evidence),
                selectinload(DocumentScreeningEvaluationRow.profile),
            )
            .where(
                DocumentScreeningEvaluationRow.process_id == process_id,
                DocumentScreeningEvaluationRow.profile_id == profile_id,
                DocumentScreeningEvaluationRow.engine_version == engine_version,
                DocumentScreeningEvaluationRow.document_set_fingerprint
                == document_set_fingerprint,
            )
        )
        if row is None:
            return None
        return self._to_evaluation(row)

    def insert_evaluation(
        self, evaluation: DocumentScreeningEvaluation, *, created_at: datetime
    ) -> None:
        if evaluation.profile_id is None:
            raise PersistenceError("avaliação documental persistida exige profile_id")
        session = self._require_session()
        session.add(
            DocumentScreeningEvaluationRow(
                id=evaluation.id,
                process_id=evaluation.process_id,
                profile_id=evaluation.profile_id,
                state=evaluation.state.value,
                reason_code=evaluation.reason_code.value,
                reason_text=evaluation.reason_text,
                engine_version=evaluation.engine_version,
                document_set_fingerprint=evaluation.document_set_fingerprint,
                evaluated_at=evaluation.evaluated_at,
                documents_considered=evaluation.coverage.documents_considered,
                sources_considered=evaluation.coverage.sources_considered,
                pages_considered=evaluation.coverage.pages_considered,
                pages_with_text=evaluation.coverage.pages_with_text,
                likely_scanned_sources=evaluation.coverage.likely_scanned_sources,
                failed_sources=evaluation.coverage.failed_sources,
                unsupported_sources=evaluation.coverage.unsupported_sources,
                complete=evaluation.coverage.complete,
                created_at=created_at,
            )
        )
        for item in evaluation.evidence:
            session.add(
                DocumentScreeningEvidenceRow(
                    id=uuid4(),
                    evaluation_id=evaluation.id,
                    extraction_page_id=item.extraction_page_id,
                    document_id=item.document_id,
                    source_id=item.source_id,
                    artifact_id=item.artifact_id,
                    category=item.category,
                    configured_term=item.configured_term,
                    matched_text=item.matched_text,
                    context_snippet=item.context_snippet,
                    page_number=item.page_number,
                    source_sha256=item.source_sha256,
                    source_path=item.source_path,
                    artifact_sha256=item.artifact_sha256,
                    negated=item.negated,
                    start_offset=item.start_offset,
                    end_offset=item.end_offset,
                    created_at=created_at,
                )
            )

    def list_evaluations_for_process(
        self, process_id: UUID
    ) -> tuple[DocumentScreeningEvaluation, ...]:
        rows = self._require_session().scalars(
            select(DocumentScreeningEvaluationRow)
            .options(
                selectinload(DocumentScreeningEvaluationRow.evidence),
                selectinload(DocumentScreeningEvaluationRow.profile),
            )
            .where(DocumentScreeningEvaluationRow.process_id == process_id)
            .order_by(DocumentScreeningEvaluationRow.evaluated_at)
        )
        return tuple(self._to_evaluation(row) for row in rows)

    def latest_initial_evaluation(
        self, process_id: UUID, profile_id: UUID
    ) -> ScreeningEvaluation | None:
        row = self._require_session().scalar(
            select(ScreeningEvaluationRow)
            .options(
                selectinload(ScreeningEvaluationRow.evidence),
                selectinload(ScreeningEvaluationRow.profile),
            )
            .where(
                ScreeningEvaluationRow.process_id == process_id,
                ScreeningEvaluationRow.profile_id == profile_id,
            )
            .order_by(ScreeningEvaluationRow.evaluated_at.desc())
            .limit(1)
        )
        if row is None:
            return None
        return evaluation_from_row(
            id=row.id,
            process_id=row.process_id,
            observation_id=row.observation_id,
            profile_id=row.profile_id,
            profile_code=row.profile.code,
            profile_version=row.profile.version,
            state=row.state,
            reason_code=row.reason_code,
            reason_text=row.reason_text,
            evaluated_at=row.evaluated_at,
            engine_version=row.engine_version,
            evidence_rows=row.evidence,
        )

    def _load_corpus(
        self, process_id: UUID, *, artifact_sha256: str | None
    ) -> DocumentScreeningCorpus:
        session = self._require_session()
        source_stmt = (
            select(
                ArtifactTextSourceRow,
                ArtifactRow,
                DocumentArtifactRow.document_id,
                TextExtractionRow,
            )
            .join(ArtifactRow, ArtifactRow.id == ArtifactTextSourceRow.artifact_id)
            .join(
                DocumentArtifactRow,
                DocumentArtifactRow.artifact_id == ArtifactRow.id,
            )
            .join(
                ProcessDocumentRow,
                ProcessDocumentRow.id == DocumentArtifactRow.document_id,
            )
            .outerjoin(
                TextExtractionRow,
                TextExtractionRow.source_id == ArtifactTextSourceRow.id,
            )
            .where(ProcessDocumentRow.process_id == process_id)
        )
        if artifact_sha256 is not None:
            source_stmt = source_stmt.where(ArtifactRow.sha256 == artifact_sha256)
        rows = session.execute(source_stmt).all()
        latest: dict[UUID, tuple] = {}
        for source, artifact, document_id, extraction in rows:
            current = latest.get(source.id)
            if current is None:
                latest[source.id] = (source, artifact, document_id, extraction)
                continue
            _source, _artifact, _document_id, existing = current
            if extraction is None:
                continue
            if existing is None or extraction.created_at >= existing.created_at:
                latest[source.id] = (source, artifact, document_id, extraction)

        sources: list[DocumentSourceRef] = []
        extraction_ids: list[UUID] = []
        source_index: dict[UUID, tuple[ArtifactTextSourceRow, ArtifactRow, UUID]] = {}
        for source, artifact, document_id, extraction in latest.values():
            status = "FAILED" if extraction is None else extraction.status
            likely = False if extraction is None else extraction.likely_scanned
            page_count = 0 if extraction is None else extraction.page_count
            pages_with_text = 0 if extraction is None else extraction.pages_with_text
            sources.append(
                DocumentSourceRef(
                    source_id=source.id,
                    source_sha256=source.sha256,
                    source_path=source.source_path,
                    artifact_id=artifact.id,
                    artifact_sha256=artifact.sha256,
                    status=status,
                    likely_scanned=likely,
                    page_count=page_count,
                    pages_with_text=pages_with_text,
                    document_id=document_id,
                )
            )
            source_index[source.id] = (source, artifact, document_id)
            if extraction is not None:
                extraction_ids.append(extraction.id)

        pages: list[DocumentPageRef] = []
        if extraction_ids:
            page_rows = session.scalars(
                select(TextExtractionPageRow)
                .where(TextExtractionPageRow.extraction_id.in_(extraction_ids))
                .order_by(
                    TextExtractionPageRow.extraction_id,
                    TextExtractionPageRow.page_number,
                )
            )
            extraction_source = {
                extraction.id: extraction.source_id
                for extraction in session.scalars(
                    select(TextExtractionRow).where(TextExtractionRow.id.in_(extraction_ids))
                )
            }
            for page in page_rows:
                source_id = extraction_source[page.extraction_id]
                source, artifact, document_id = source_index[source_id]
                pages.append(
                    DocumentPageRef(
                        extraction_page_id=page.id,
                        page_number=page.page_number,
                        text=page.text,
                        source_id=source.id,
                        source_sha256=source.sha256,
                        source_path=source.source_path,
                        artifact_id=artifact.id,
                        artifact_sha256=artifact.sha256,
                        document_id=document_id,
                    )
                )
        return DocumentScreeningCorpus(
            process_id=process_id,
            pages=tuple(pages),
            sources=tuple(sources),
        )

    def _to_evaluation(
        self, row: DocumentScreeningEvaluationRow
    ) -> DocumentScreeningEvaluation:
        return document_evaluation_from_row(
            id=row.id,
            process_id=row.process_id,
            profile_id=row.profile_id,
            profile_code=row.profile.code,
            profile_version=row.profile.version,
            state=row.state,
            reason_code=row.reason_code,
            reason_text=row.reason_text,
            evaluated_at=row.evaluated_at,
            engine_version=row.engine_version,
            document_set_fingerprint=row.document_set_fingerprint,
            documents_considered=row.documents_considered,
            sources_considered=row.sources_considered,
            pages_considered=row.pages_considered,
            pages_with_text=row.pages_with_text,
            likely_scanned_sources=row.likely_scanned_sources,
            failed_sources=row.failed_sources,
            unsupported_sources=row.unsupported_sources,
            complete=row.complete,
            evidence_rows=row.evidence,
        )

    def _require_session(self) -> Session:
        if self._session is None:
            raise PersistenceError("operação fora de transação")
        return self._session
