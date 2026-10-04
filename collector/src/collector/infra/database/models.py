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
    Integer,
    MetaData,
    Numeric,
    Text,
    UniqueConstraint,
    Uuid,
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
