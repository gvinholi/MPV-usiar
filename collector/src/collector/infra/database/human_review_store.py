"""PostgreSQL human audit trail; no writes to earlier layers.

READ COMMITTED: latest is checked in the insert transaction. A concurrent
resolution may still commit after this check; queries then derive STALE.
"""
from datetime import UTC
from uuid import uuid4

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Column, DateTime, ForeignKey, Identity, Index, Table, Text,
    Uuid, func, select, text,
)
from sqlalchemy.dialects.postgresql import insert

from collector.application.human_review.models import (
    HumanReview, HumanReviewDecision, HumanReviewReason, HumanReviewStatus,
    HumanReviewSummary, IdempotencyConflictError, RecordHumanReviewCommand,
    ReviewerIdentity, ReviewQueue, ReviewQueueItem, check_stale, derive_status,
    ALLOWED_REASONS, validate_command, in_queue,
)
from collector.application.human_review_errors import OperationalResolutionNotFoundError
from collector.infra.database.models import Base, OperationalResolutionRow
from collector.infra.database.resolution_store import _LATEST

# Process/profile are normalized through the mandatory resolution FK. They cannot
# disagree with the reviewed resolution; DTOs expose them through joins.
human_reviews = Table(
    "human_reviews", Base.metadata,
    Column("id", Uuid, primary_key=True),
    Column("sequence", BigInteger, Identity(), nullable=False, unique=True),
    Column("operational_resolution_id", Uuid, ForeignKey("operational_resolutions.id"), nullable=False),
    Column("reviewer_id", Text, nullable=False),
    Column("reviewer_display_name", Text),
    Column("decision", Text, nullable=False),
    Column("reason_code", Text, nullable=False),
    Column("comment", Text),
    Column("idempotency_key", Text, nullable=False, unique=True),
    Column("allow_stale", Boolean, nullable=False),
    Column("was_stale_at_decision", Boolean, nullable=False),
    Column("latest_resolution_id_at_decision", Uuid, ForeignKey("operational_resolutions.id"), nullable=False),
    Column("resolution_fingerprint", Text, nullable=False),
    Column("operational_state_snapshot", Text, nullable=False),
    Column("decided_at", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("decision IN ('SELECTED','DISCARDED','PENDING')", name="human_decision"),
    CheckConstraint(" OR ".join(
        f"(decision = '{decision.value}' AND reason_code IN ({','.join(repr(r.value) for r in sorted(reasons))}))"
        for decision, reasons in ALLOWED_REASONS.items()
    ), name="human_reason_compatibility"),
    CheckConstraint("reason_code <> 'OTHER' OR (comment IS NOT NULL AND comment ~ '[^[:space:]]')", name="human_other_comment"),
    CheckConstraint("comment IS NULL OR length(comment) <= 4000", name="human_comment_length"),
    CheckConstraint("reviewer_id ~ '[^[:space:]]' AND length(reviewer_id) <= 200", name="human_reviewer"),
    CheckConstraint("reviewer_display_name IS NULL OR (reviewer_display_name ~ '[^[:space:]]' AND length(reviewer_display_name) <= 200)", name="human_display_name"),
    CheckConstraint("idempotency_key ~ '[^[:space:]]' AND length(idempotency_key) <= 200", name="human_key"),
    CheckConstraint("operational_state_snapshot IN ('CANDIDATE','PENDING','DISCARDED')", name="human_operational_state"),
    CheckConstraint("was_stale_at_decision = (operational_resolution_id <> latest_resolution_id_at_decision) AND (NOT was_stale_at_decision OR allow_stale)", name="human_stale_audit"),
    Index("ix_human_reviews_latest", "operational_resolution_id", "decided_at", "created_at", "sequence"),
)
H = human_reviews.c
R = OperationalResolutionRow
REVIEW_ORDER = (H.decided_at.desc(), H.created_at.desc(), H.sequence.desc())


def _review(row):
    command = RecordHumanReviewCommand(
        operational_resolution_id=row.operational_resolution_id,
        reviewer=ReviewerIdentity(row.reviewer_id, row.reviewer_display_name),
        decision=HumanReviewDecision(row.decision), reason=HumanReviewReason(row.reason_code),
        idempotency_key=row.idempotency_key, comment=row.comment, allow_stale=row.allow_stale,
    )
    return HumanReview(
        row.id, row.process_id, row.profile_id, command, row.was_stale_at_decision,
        row.latest_resolution_id_at_decision, row.resolution_fingerprint,
        row.operational_state_snapshot, row.decided_at, row.created_at, row.sequence,
    )


def _reviews_stmt():
    return select(human_reviews, R.process_id, R.profile_id).join(R, R.id == H.operational_resolution_id)


def _retry(row, command):
    review = _review(row)
    if review.command != command:
        raise IdempotencyConflictError(f"idempotency key already used: {command.idempotency_key}")
    return review


class SqlAlchemyHumanReviewRepository:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    def record(self, command, *, clock):
        validate_command(command)
        with self._session_factory.begin() as session:
            # Serialize retries of this key before stale checking. Hash collisions
            # only cause extra waiting, never data loss. UNIQUE remains authoritative.
            session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                            {"key": command.idempotency_key})
            existing = session.execute(_reviews_stmt().where(H.idempotency_key == command.idempotency_key)).first()
            if existing:
                return _retry(existing, command)
            resolution = session.get(R, command.operational_resolution_id)
            if resolution is None:
                raise OperationalResolutionNotFoundError(str(command.operational_resolution_id))
            latest = session.scalar(select(R).where(
                R.process_id == resolution.process_id, R.profile_id == resolution.profile_id,
            ).order_by(*_LATEST).limit(1))
            stale = check_stale(command, latest.id)
            now = clock()
            if now.tzinfo is None or now.utcoffset() is None:
                raise ValueError("clock must return an aware timestamp")
            now = now.astimezone(UTC)
            inserted_id = session.scalar(insert(human_reviews).values(
                id=uuid4(), operational_resolution_id=resolution.id,
                reviewer_id=command.reviewer.reviewer_id,
                reviewer_display_name=command.reviewer.display_name,
                decision=command.decision.value, reason_code=command.reason.value,
                comment=command.comment, idempotency_key=command.idempotency_key,
                allow_stale=command.allow_stale, was_stale_at_decision=stale,
                latest_resolution_id_at_decision=latest.id,
                resolution_fingerprint=resolution.resolution_fingerprint,
                operational_state_snapshot=resolution.state,
                decided_at=now, created_at=now,
            ).on_conflict_do_nothing(index_elements=[H.idempotency_key]).returning(H.id))
            # ON CONFLICT waits for a concurrent winner. A fresh statement sees
            # that committed row at READ COMMITTED, then verifies the full payload.
            row = session.execute(_reviews_stmt().where(H.idempotency_key == command.idempotency_key)).one()
            return _review(row) if inserted_id else _retry(row, command)

    def latest_review_for_resolution(self, resolution_id):
        with self._session_factory() as session:
            row = session.execute(_reviews_stmt().where(H.operational_resolution_id == resolution_id).order_by(*REVIEW_ORDER).limit(1)).first()
            return _review(row) if row else None

    def list_reviews_for_process(self, process_id, profile_id):
        with self._session_factory() as session:
            return tuple(_review(row) for row in session.execute(_reviews_stmt().where(
                R.process_id == process_id, R.profile_id == profile_id,
            ).order_by(*REVIEW_ORDER)))

    def _current_items(self, session, *, process_id=None, profile_id=None):
        ranked = select(R.id, func.row_number().over(
            partition_by=(R.process_id, R.profile_id), order_by=_LATEST,
        ).label("rn")).subquery()
        review_ranked = select(H.operational_resolution_id, H.id, func.row_number().over(
            partition_by=H.operational_resolution_id, order_by=REVIEW_ORDER,
        ).label("rn")).subquery()
        prior = R.__table__.alias("prior_resolution")
        history = select(H.id).join(prior, prior.c.id == H.operational_resolution_id).where(
            prior.c.process_id == R.process_id, prior.c.profile_id == R.profile_id,
        ).correlate(R).exists()
        stmt = select(R, H.decision, H.reason_code, H.reviewer_id,
                      H.reviewer_display_name, H.decided_at, H.id, history.label("history")).join(
            ranked, (ranked.c.id == R.id) & (ranked.c.rn == 1),
        ).outerjoin(review_ranked, (review_ranked.c.operational_resolution_id == R.id) & (review_ranked.c.rn == 1)).outerjoin(
            human_reviews, H.id == review_ranked.c.id,
        ).order_by(*_LATEST, R.process_id, R.profile_id)
        if process_id is not None:
            stmt = stmt.where(R.process_id == process_id)
        if profile_id is not None:
            stmt = stmt.where(R.profile_id == profile_id)
        items = []
        for row in session.execute(stmt):
            resolution = row[0]
            items.append(ReviewQueueItem(
                resolution.process_id, resolution.profile_id, resolution.id,
                resolution.state, resolution.reason_code, resolution.resolved_at,
                derive_status(row.id is not None, row.history),
                HumanReviewDecision(row.decision) if row.decision else None,
                HumanReviewReason(row.reason_code) if row.reason_code else None,
                ReviewerIdentity(row.reviewer_id, row.reviewer_display_name) if row.reviewer_id else None,
                row.decided_at,
            ))
        return tuple(items)

    def review_status_for_process(self, process_id, profile_id):
        with self._session_factory() as session:
            items = self._current_items(session, process_id=process_id, profile_id=profile_id)
            return items[0] if items else None

    def list_queue(self, queue=None, *, profile_id=None, include_operational_discarded=False):
        with self._session_factory() as session:
            items = self._current_items(session, profile_id=profile_id)
        return tuple(item for item in items if in_queue(item, queue, include_operational_discarded))

    def summary(self, *, profile_id=None):
        # REPEATABLE READ keeps both reads on one snapshot without writer locks.
        with self._session_factory() as session:
            session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
            items = self._current_items(session, profile_id=profile_id)
            stmt = select(func.count(H.id), func.count(H.id).filter(H.was_stale_at_decision)).join(R, R.id == H.operational_resolution_id)
            if profile_id is not None:
                stmt = stmt.where(R.profile_id == profile_id)
            total, overrides = session.execute(stmt).one()
        return HumanReviewSummary(
            len(items), sum(in_queue(x, ReviewQueue.NEEDS_REVIEW, False) for x in items),
            sum(x.human_review_status == HumanReviewStatus.REVIEWED for x in items),
            sum(x.human_review_status == HumanReviewStatus.STALE for x in items),
            sum(x.human_decision == HumanReviewDecision.SELECTED for x in items),
            sum(x.human_decision == HumanReviewDecision.DISCARDED for x in items),
            sum(x.human_decision == HumanReviewDecision.PENDING for x in items), total, overrides,
        )
