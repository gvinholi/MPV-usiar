"""Modelos SQLAlchemy de persistência. Não são entidades de domínio."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    Numeric,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class CollectionRoundRow(Base):
    __tablename__ = "collection_rounds"
    __table_args__ = (
        CheckConstraint(
            "status IN ('RUNNING', 'SUCCESS', 'PARTIAL', 'FAILED')",
            name="status",
        ),
        CheckConstraint("source IN ('PNCP', 'RHS')", name="source"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, nullable=False)
    pages_expected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pages_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pages_with_error: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_collected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unique_processes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    candidates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    selected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pending: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discarded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    documents_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    modality_outcomes: Mapped[list[ModalityOutcomeRow]] = relationship(
        back_populates="collection_round"
    )
    observations: Mapped[list[ProcessObservationRow]] = relationship(
        back_populates="collection_round"
    )


class ModalityOutcomeRow(Base):
    __tablename__ = "collection_modality_outcomes"
    __table_args__ = (
        UniqueConstraint("round_id", "modality_code", name="uq_modality_outcomes_round_code"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    round_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("collection_rounds.id"), nullable=False, index=True
    )
    modality_code: Mapped[int] = mapped_column(Integer, nullable=False)
    complete: Mapped[bool] = mapped_column(Boolean, nullable=False)
    pages_processed: Mapped[int] = mapped_column(Integer, nullable=False)
    records_received: Mapped[int] = mapped_column(Integer, nullable=False)
    processes_mapped: Mapped[int] = mapped_column(Integer, nullable=False)
    failed_page: Mapped[int | None] = mapped_column(Integer)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    mapping_errors: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    collection_round: Mapped[CollectionRoundRow] = relationship(
        back_populates="modality_outcomes"
    )


class ProcessRow(Base):
    __tablename__ = "processes"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    identities: Mapped[list[SourceIdentityRow]] = relationship(back_populates="process")
    observations: Mapped[list[ProcessObservationRow]] = relationship(
        back_populates="process"
    )


class SourceIdentityRow(Base):
    __tablename__ = "source_identities"
    __table_args__ = (
        UniqueConstraint("source", "official_id", name="uq_source_identities_source_official"),
        CheckConstraint("source IN ('PNCP', 'RHS')", name="source"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    process_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("processes.id"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    official_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    process: Mapped[ProcessRow] = relationship(back_populates="identities")


class ProcessObservationRow(Base):
    __tablename__ = "process_observations"
    __table_args__ = (
        UniqueConstraint(
            "round_id", "process_id", name="uq_process_observations_round_process"
        ),
        CheckConstraint("source IN ('PNCP', 'RHS')", name="source"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    process_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("processes.id"), nullable=False, index=True
    )
    round_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("collection_rounds.id"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    organization_name: Mapped[str | None] = mapped_column(Text)
    organization_cnpj: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    modality: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    state: Mapped[str | None] = mapped_column(Text)
    locality: Mapped[str | None] = mapped_column(Text)
    estimated_value: Mapped[Decimal | None] = mapped_column(Numeric)
    notice_number: Mapped[str | None] = mapped_column(Text)
    official_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    process: Mapped[ProcessRow] = relationship(back_populates="observations")
    collection_round: Mapped[CollectionRoundRow] = relationship(
        back_populates="observations"
    )
    evaluations: Mapped[list[ScreeningEvaluationRow]] = relationship(
        back_populates="observation"
    )


class ScreeningProfileRow(Base):
    __tablename__ = "screening_profiles"
    __table_args__ = (
        UniqueConstraint("code", "version", name="uq_screening_profiles_code_version"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    configuration: Mapped[dict[str, list[str]]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    evaluations: Mapped[list[ScreeningEvaluationRow]] = relationship(
        back_populates="profile"
    )
    document_evaluations: Mapped[list[DocumentScreeningEvaluationRow]] = relationship(
        back_populates="profile"
    )


class ScreeningEvaluationRow(Base):
    __tablename__ = "screening_evaluations"
    __table_args__ = (
        UniqueConstraint(
            "observation_id",
            "profile_id",
            "engine_version",
            name="uq_screening_evaluations_observation_profile_engine",
        ),
        CheckConstraint(
            "state IN ('CANDIDATE', 'PENDING', 'DISCARDED')",
            name="state",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    process_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("processes.id"), nullable=False, index=True
    )
    observation_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("process_observations.id"), nullable=False, index=True
    )
    profile_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("screening_profiles.id"), nullable=False, index=True
    )
    state: Mapped[str] = mapped_column(Text, nullable=False)
    reason_code: Mapped[str] = mapped_column(Text, nullable=False)
    reason_text: Mapped[str] = mapped_column(Text, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    engine_version: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    process: Mapped[ProcessRow] = relationship()
    observation: Mapped[ProcessObservationRow] = relationship(
        back_populates="evaluations"
    )
    profile: Mapped[ScreeningProfileRow] = relationship(back_populates="evaluations")
    evidence: Mapped[list[ScreeningEvidenceRow]] = relationship(
        back_populates="evaluation"
    )


class ScreeningEvidenceRow(Base):
    __tablename__ = "screening_evidence"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    evaluation_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("screening_evaluations.id"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(Text, nullable=False)
    configured_term: Mapped[str] = mapped_column(Text, nullable=False)
    field: Mapped[str] = mapped_column(Text, nullable=False)
    matched_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    evaluation: Mapped[ScreeningEvaluationRow] = relationship(back_populates="evidence")


class ProcessDocumentRow(Base):
    __tablename__ = "process_documents"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "official_document_id",
            name="uq_process_documents_source_official",
        ),
        CheckConstraint("source IN ('PNCP', 'RHS')", name="source"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    process_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("processes.id"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    official_document_id: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    document_type: Mapped[str | None] = mapped_column(Text)
    document_type_id: Mapped[int | None] = mapped_column(Integer)
    document_type_description: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool | None] = mapped_column(Boolean)
    document_sequence: Mapped[int | None] = mapped_column(Integer)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DocumentCatalogQueryRow(Base):
    __tablename__ = "document_catalog_queries"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    process_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("processes.id"), nullable=False, index=True
    )
    round_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("collection_rounds.id"), index=True
    )
    documents_found: Mapped[int] = mapped_column(Integer, nullable=False)
    complete: Mapped[bool] = mapped_column(Boolean, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    queried_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DocumentObservationRow(Base):
    __tablename__ = "document_observations"
    __table_args__ = (
        UniqueConstraint(
            "query_id",
            "document_id",
            name="uq_document_observations_query_document",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    query_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("document_catalog_queries.id"), nullable=False, index=True
    )
    document_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("process_documents.id"), nullable=False, index=True
    )
    process_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("processes.id"), nullable=False, index=True
    )
    title: Mapped[str | None] = mapped_column(Text)
    document_type: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool | None] = mapped_column(Boolean)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ArtifactRow(Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        UniqueConstraint("sha256", name="uq_artifacts_sha256"),
        CheckConstraint("hash_algorithm = 'sha256'", name="hash_algorithm"),
        CheckConstraint(
            "detected_type IN ('PDF', 'ZIP', 'UNKNOWN')",
            name="detected_type",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    sha256: Mapped[str] = mapped_column(Text, nullable=False)
    hash_algorithm: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    detected_type: Mapped[str] = mapped_column(Text, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DocumentArtifactRow(Base):
    __tablename__ = "document_artifacts"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    document_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("process_documents.id"), nullable=False, index=True
    )
    artifact_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("artifacts.id"), index=True
    )
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    requested_url: Mapped[str | None] = mapped_column(Text)
    final_url: Mapped[str | None] = mapped_column(Text)
    http_status: Mapped[int | None] = mapped_column(Integer)
    http_content_type: Mapped[str | None] = mapped_column(Text)
    original_filename: Mapped[str | None] = mapped_column(Text)
    complete: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason_code: Mapped[str | None] = mapped_column(Text)
    bytes_received: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ArtifactArchiveEntryRow(Base):
    __tablename__ = "artifact_archive_entries"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    artifact_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("artifacts.id"), nullable=False, index=True
    )
    original_path: Mapped[str] = mapped_column(Text, nullable=False)
    compressed_size: Mapped[int | None] = mapped_column(Integer)
    uncompressed_size: Mapped[int | None] = mapped_column(Integer)
    is_directory: Mapped[bool] = mapped_column(Boolean, nullable=False)
    extension: Mapped[str | None] = mapped_column(Text)
    is_encrypted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_symlink: Mapped[bool] = mapped_column(Boolean, nullable=False)
    has_unsafe_path: Mapped[bool] = mapped_column(Boolean, nullable=False)
    unsafe_path_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ArtifactTextSourceRow(Base):
    __tablename__ = "artifact_text_sources"
    __table_args__ = (
        UniqueConstraint(
            "artifact_id",
            "source_path",
            "sha256",
            name="uq_artifact_text_sources_artifact_path_sha",
        ),
        CheckConstraint(
            "detected_type IN ('PDF', 'ZIP', 'UNKNOWN')",
            name="detected_type",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    artifact_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("artifacts.id"), nullable=False, index=True
    )
    archive_entry_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("artifact_archive_entries.id")
    )
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    detected_type: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TextExtractionRow(Base):
    __tablename__ = "text_extractions"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "extractor_name",
            "extractor_version",
            name="uq_text_extractions_source_extractor_version",
        ),
        CheckConstraint(
            "status IN ('DIGITAL_TEXT', 'EMPTY_TEXT', 'LIKELY_SCANNED', 'FAILED', 'UNSUPPORTED')",
            name="status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    source_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("artifact_text_sources.id"), nullable=False, index=True
    )
    extractor_name: Mapped[str] = mapped_column(Text, nullable=False)
    extractor_version: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    pages_with_text: Mapped[int] = mapped_column(Integer, nullable=False)
    character_count: Mapped[int] = mapped_column(Integer, nullable=False)
    likely_scanned: Mapped[bool] = mapped_column(Boolean, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    error_code: Mapped[str | None] = mapped_column(Text)
    error_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TextExtractionPageRow(Base):
    __tablename__ = "text_extraction_pages"
    __table_args__ = (
        UniqueConstraint(
            "extraction_id",
            "page_number",
            name="uq_text_extraction_pages_extraction_page",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    extraction_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("text_extractions.id"), nullable=False, index=True
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DocumentScreeningEvaluationRow(Base):
    __tablename__ = "document_screening_evaluations"
    __table_args__ = (
        UniqueConstraint(
            "process_id",
            "profile_id",
            "engine_version",
            "document_set_fingerprint",
            name="uq_doc_screening_eval_process_profile_engine_fp",
        ),
        CheckConstraint(
            "state IN ('CANDIDATE', 'PENDING', 'DISCARDED')",
            name="state",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    process_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("processes.id"), nullable=False, index=True
    )
    profile_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("screening_profiles.id"), nullable=False, index=True
    )
    state: Mapped[str] = mapped_column(Text, nullable=False)
    reason_code: Mapped[str] = mapped_column(Text, nullable=False)
    reason_text: Mapped[str] = mapped_column(Text, nullable=False)
    engine_version: Mapped[str] = mapped_column(Text, nullable=False)
    document_set_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    documents_considered: Mapped[int] = mapped_column(Integer, nullable=False)
    sources_considered: Mapped[int] = mapped_column(Integer, nullable=False)
    pages_considered: Mapped[int] = mapped_column(Integer, nullable=False)
    pages_with_text: Mapped[int] = mapped_column(Integer, nullable=False)
    likely_scanned_sources: Mapped[int] = mapped_column(Integer, nullable=False)
    failed_sources: Mapped[int] = mapped_column(Integer, nullable=False)
    unsupported_sources: Mapped[int] = mapped_column(Integer, nullable=False)
    complete: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    process: Mapped[ProcessRow] = relationship()
    profile: Mapped[ScreeningProfileRow] = relationship(
        back_populates="document_evaluations"
    )
    evidence: Mapped[list[DocumentScreeningEvidenceRow]] = relationship(
        back_populates="evaluation"
    )


class DocumentScreeningEvidenceRow(Base):
    __tablename__ = "document_screening_evidence"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    evaluation_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("document_screening_evaluations.id"),
        nullable=False,
        index=True,
    )
    extraction_page_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("text_extraction_pages.id"), nullable=False, index=True
    )
    document_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("process_documents.id")
    )
    source_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("artifact_text_sources.id"), nullable=False
    )
    artifact_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("artifacts.id"), nullable=False
    )
    category: Mapped[str] = mapped_column(Text, nullable=False)
    configured_term: Mapped[str] = mapped_column(Text, nullable=False)
    matched_text: Mapped[str] = mapped_column(Text, nullable=False)
    context_snippet: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    negated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    evaluation: Mapped[DocumentScreeningEvaluationRow] = relationship(
        back_populates="evidence"
    )


class OperationalResolutionRow(Base):
    __tablename__ = "operational_resolutions"
    __table_args__ = (
        UniqueConstraint(
            "process_id",
            "profile_id",
            "resolver_engine_version",
            "resolution_fingerprint",
            name="uq_operational_res_process_profile_engine_fp",
        ),
        CheckConstraint(
            "state IN ('CANDIDATE', 'PENDING', 'DISCARDED')",
            name="state",
        ),
        CheckConstraint(
            "initial_state IN ('CANDIDATE', 'PENDING', 'DISCARDED')",
            name="initial_state",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    process_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("processes.id"), nullable=False, index=True
    )
    profile_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("screening_profiles.id"), nullable=False, index=True
    )
    initial_evaluation_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("screening_evaluations.id"), nullable=False, index=True
    )
    document_evaluation_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("document_screening_evaluations.id"), index=True
    )
    resolver_engine_version: Mapped[str] = mapped_column(Text, nullable=False)
    resolution_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    reason_code: Mapped[str] = mapped_column(Text, nullable=False)
    reason_text: Mapped[str] = mapped_column(Text, nullable=False)
    rule_code: Mapped[str] = mapped_column(Text, nullable=False)
    coverage_complete: Mapped[bool] = mapped_column(Boolean, nullable=False)
    state_diverged: Mapped[bool | None] = mapped_column(Boolean)
    reason_diverged: Mapped[bool | None] = mapped_column(Boolean)
    initial_state: Mapped[str] = mapped_column(Text, nullable=False)
    document_state: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    process: Mapped[ProcessRow] = relationship()
    profile: Mapped[ScreeningProfileRow] = relationship()


class AuthUserRow(Base):
    __tablename__ = "auth_users"
    __table_args__ = (
        UniqueConstraint("normalized_email", name="uq_auth_users_normalized_email"),
        CheckConstraint("length(email) BETWEEN 3 AND 320", name="email_length"),
        CheckConstraint("length(normalized_email) BETWEEN 3 AND 320", name="normalized_email_length"),
        CheckConstraint("normalized_email = lower(normalized_email)", name="normalized_email_lower"),
        CheckConstraint("password_hash LIKE '$argon2id$%'", name="argon2id"),
        CheckConstraint("password_version >= 1", name="password_version"),
        CheckConstraint("display_name IS NULL OR (display_name ~ '[^[:space:]]' AND length(display_name) <= 200)", name="display_name"),
        CheckConstraint("updated_at >= created_at", name="timestamp_order"),
        CheckConstraint("(active AND disabled_at IS NULL) OR (NOT active AND disabled_at IS NOT NULL)", name="active_state"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_email: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    password_version: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthPermissionRow(Base):
    __tablename__ = "auth_permissions"
    __table_args__ = (
        CheckConstraint(
            "code ~ '^[a-z][a-z0-9_-]{0,31}:[a-z][a-z0-9_-]{0,31}$'",
            name="code",
        ),
        CheckConstraint("description ~ '[^[:space:]]' AND length(description) <= 200", name="description"),
    )

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AuthUserPermissionRow(Base):
    __tablename__ = "auth_user_permissions"

    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("auth_users.id"), primary_key=True)
    permission_code: Mapped[str] = mapped_column(Text, ForeignKey("auth_permissions.code"), primary_key=True, index=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    granted_by: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("auth_users.id"))


class AuthSessionRow(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        UniqueConstraint("verifier_digest", name="uq_auth_sessions_verifier_digest"),
        CheckConstraint("octet_length(verifier_digest) = 32", name="verifier_digest"),
        CheckConstraint("octet_length(csrf_digest) = 32", name="csrf_digest"),
        CheckConstraint("password_version >= 1", name="password_version"),
        CheckConstraint("last_seen_at >= created_at", name="last_seen"),
        CheckConstraint("last_seen_at < idle_expires_at", name="last_seen_expiration"),
        CheckConstraint("idle_expires_at > created_at AND idle_expires_at <= absolute_expires_at", name="idle_expiration"),
        CheckConstraint("absolute_expires_at > created_at", name="absolute_expiration"),
        CheckConstraint("(revoked_at IS NULL AND revoke_reason IS NULL) OR (revoked_at IS NOT NULL AND revoke_reason ~ '[^[:space:]]' AND length(revoke_reason) <= 100)", name="revocation"),
        Index(
            "ix_auth_sessions_expiration",
            "absolute_expires_at",
            "idle_expires_at",
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    verifier_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    csrf_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("auth_users.id"), nullable=False, index=True)
    password_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idle_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(Text)


class AuthLoginAttemptRow(Base):
    __tablename__ = "auth_login_attempts"
    __table_args__ = (
        CheckConstraint("octet_length(key_digest) = 32", name="key_digest"),
        CheckConstraint("failure_count >= 0", name="failure_count"),
        CheckConstraint("last_failure_at >= window_started_at", name="failure_order"),
        CheckConstraint("updated_at >= created_at", name="update_order"),
        CheckConstraint("blocked_until IS NULL OR blocked_until > last_failure_at", name="block_order"),
        Index(
            "ix_auth_login_attempts_blocked_until",
            "blocked_until",
            postgresql_where=text("blocked_until IS NOT NULL"),
        ),
    )

    key_digest: Mapped[bytes] = mapped_column(LargeBinary, primary_key=True)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_failure_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AuthAuditEventRow(Base):
    __tablename__ = "auth_audit_events"
    __table_args__ = (
        CheckConstraint("event_type ~ '^[A-Z][A-Z0-9_]{0,63}$'", name="type"),
        CheckConstraint("outcome IN ('SUCCESS','FAILURE')", name="outcome"),
        CheckConstraint("request_id IS NULL OR request_id ~ '^[A-Za-z0-9._:-]{1,128}$'", name="request_id"),
        CheckConstraint("created_at >= occurred_at", name="timestamp_order"),
        Index("ix_auth_audit_events_subject_time", "subject_user_id", "occurred_at"),
        Index("ix_auth_audit_events_type_time", "event_type", "occurred_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    subject_user_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("auth_users.id"))
    actor_user_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("auth_users.id"))
    request_id: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

