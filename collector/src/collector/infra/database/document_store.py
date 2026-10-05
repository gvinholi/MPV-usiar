"""Repositório PostgreSQL do catálogo documental."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from collector.application.documents.results import DocumentCatalogResult
from collector.application.persistence.errors import PersistenceError
from collector.domain import ProcurementDocument
from collector.infra.database.models import (
    DocumentCatalogQueryRow,
    DocumentObservationRow,
    ProcessDocumentRow,
)


class SqlAlchemyDocumentCatalogRepository:
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

    def get_query(self, query_id: UUID) -> DocumentCatalogResult | None:
        row = self._require_session().get(DocumentCatalogQueryRow, query_id)
        if row is None:
            return None
        return DocumentCatalogResult(
            query_id=row.id,
            process_id=row.process_id,
            round_id=row.round_id,
            documents=(),
            documents_found=row.documents_found,
            complete=row.complete,
            queried_at=row.queried_at,
            errors=(),
            failure_reason=row.failure_reason,
        )

    def find_document(self, source: str, official_id: str) -> tuple[UUID, UUID] | None:
        row = self._require_session().scalar(
            select(ProcessDocumentRow).where(
                ProcessDocumentRow.source == source,
                ProcessDocumentRow.official_document_id == official_id,
            )
        )
        if row is None:
            return None
        return row.id, row.process_id

    def insert_query(self, result: DocumentCatalogResult, *, created_at: datetime) -> None:
        session = self._require_session()
        session.add(
            DocumentCatalogQueryRow(
                id=result.query_id,
                process_id=result.process_id,
                round_id=result.round_id,
                documents_found=result.documents_found,
                complete=result.complete,
                failure_reason=result.failure_reason,
                queried_at=result.queried_at,
                created_at=created_at,
            )
        )
        session.flush()

    def insert_document(
        self, document: ProcurementDocument, *, seen_at: datetime
    ) -> None:
        session = self._require_session()
        session.add(
            ProcessDocumentRow(
                id=document.id,
                process_id=document.process_id,
                source=document.identity.source.value,
                official_document_id=document.identity.official_id,
                title=document.title,
                document_type=document.document_type,
                document_type_id=document.document_type_id,
                document_type_description=document.document_type_description,
                url=document.url,
                published_at=document.published_at,
                is_active=document.active,
                document_sequence=document.sequence,
                first_seen_at=seen_at,
                last_seen_at=seen_at,
                created_at=seen_at,
                updated_at=seen_at,
            )
        )
        session.flush()

    def touch_document(
        self,
        document_id: UUID,
        document: ProcurementDocument,
        *,
        seen_at: datetime,
    ) -> None:
        row = self._require_session().get(ProcessDocumentRow, document_id)
        if row is None:
            raise PersistenceError("documento persistente não encontrado")
        row.last_seen_at = seen_at
        row.updated_at = seen_at
        row.title = document.title
        row.document_type = document.document_type
        row.document_type_id = document.document_type_id
        row.document_type_description = document.document_type_description
        row.url = document.url
        row.published_at = document.published_at
        row.is_active = document.active
        row.document_sequence = document.sequence

    def has_observation(self, query_id: UUID, document_id: UUID) -> bool:
        row = self._require_session().scalar(
            select(DocumentObservationRow.id).where(
                DocumentObservationRow.query_id == query_id,
                DocumentObservationRow.document_id == document_id,
            )
        )
        return row is not None

    def insert_observation(
        self,
        *,
        query_id: UUID,
        document: ProcurementDocument,
        created_at: datetime,
    ) -> None:
        self._require_session().add(
            DocumentObservationRow(
                id=uuid4(),
                query_id=query_id,
                document_id=document.id,
                process_id=document.process_id,
                title=document.title,
                document_type=document.document_type,
                url=document.url,
                published_at=document.published_at,
                is_active=document.active,
                observed_at=created_at,
                created_at=created_at,
            )
        )

    def _require_session(self) -> Session:
        if self._session is None:
            raise PersistenceError("operação fora de transação")
        return self._session
