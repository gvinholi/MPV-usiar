"""Persistência contra PostgreSQL real."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from collector.application import (
    IdentityConflictError,
    PersistCollection,
    PersistOutcome,
)
from collector.domain import RoundStatus, Source
from tests.application.persistence.factories import (
    collection_result,
    identity,
    outcome,
    process,
)

pytestmark = pytest.mark.postgres


def _counts(session: Session) -> dict[str, int]:
    tables = (
        "collection_rounds",
        "collection_modality_outcomes",
        "processes",
        "source_identities",
        "process_observations",
    )
    return {
        table: session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
        for table in tables
    }


def test_first_observation(persist_service: PersistCollection, db_session: Session) -> None:
    snapshot = process("123")
    persist_service.persist(collection_result(snapshot))

    counts = _counts(db_session)
    assert counts == {
        "collection_rounds": 1,
        "collection_modality_outcomes": 1,
        "processes": 1,
        "source_identities": 1,
        "process_observations": 1,
    }
    official = db_session.execute(
        text("SELECT source, official_id FROM source_identities")
    ).one()
    assert official == ("PNCP", "123")


def test_same_process_new_round_keeps_history(
    persist_service: PersistCollection, db_session: Session
) -> None:
    first = process(
        "123",
        closes_at=datetime(2026, 10, 10, 18, 0, tzinfo=UTC),
        estimated_value=Decimal("10000.00"),
    )
    persist_service.persist(collection_result(first, round_id=uuid4()))
    second = process(
        "123",
        process_id=uuid4(),
        closes_at=datetime(2026, 10, 15, 18, 0, tzinfo=UTC),
        estimated_value=Decimal("10000.00"),
        last_captured_at=datetime(2026, 10, 4, 14, 0, tzinfo=UTC),
    )
    persist_service.persist(collection_result(second, round_id=uuid4()))

    counts = _counts(db_session)
    assert counts["processes"] == 1
    assert counts["source_identities"] == 1
    assert counts["process_observations"] == 2
    assert counts["collection_rounds"] == 2
    rows = db_session.execute(
        text(
            "SELECT closes_at, estimated_value FROM process_observations "
            "ORDER BY captured_at"
        )
    ).all()
    assert rows[0][0].day == 10
    assert rows[1][0].day == 15
    assert rows[0][1] == Decimal("10000.00")
    assert isinstance(rows[1][1], Decimal)
    assert rows[0][0].tzinfo is not None
    process_id = db_session.execute(text("SELECT id FROM processes")).scalar_one()
    assert process_id == first.id


def test_same_result_twice_does_not_duplicate(
    persist_service: PersistCollection, db_session: Session
) -> None:
    result = collection_result(
        process(
            "123",
            notice_number="EDITAL-42/2026",
            official_url="https://example.gov.br/contratacao/42",
        )
    )
    first = persist_service.persist(result)
    second = persist_service.persist(result)

    assert first.created is True
    assert second.created is False
    assert _counts(db_session)["collection_rounds"] == 1
    assert _counts(db_session)["process_observations"] == 1
    assert _counts(db_session)["source_identities"] == 1
    fields = db_session.execute(
        text("SELECT notice_number, official_url FROM process_observations")
    ).one()
    assert fields == ("EDITAL-42/2026", "https://example.gov.br/contratacao/42")


def test_new_null_snapshot_does_not_overwrite_historical_official_fields(
    persist_service: PersistCollection, db_session: Session
) -> None:
    first = process(
        "123",
        notice_number="EDITAL-42/2026",
        official_url="https://example.gov.br/contratacao/42",
    )
    persist_service.persist(collection_result(first, round_id=uuid4()))
    later = process(
        "123",
        process_id=uuid4(),
        notice_number=None,
        official_url=None,
        last_captured_at=datetime(2026, 10, 5, 14, 0, tzinfo=UTC),
    )
    persist_service.persist(collection_result(later, round_id=uuid4()))

    rows = db_session.execute(
        text(
            "SELECT notice_number, official_url FROM process_observations "
            "ORDER BY captured_at"
        )
    ).all()
    assert rows == [
        ("EDITAL-42/2026", "https://example.gov.br/contratacao/42"),
        (None, None),
    ]


def test_new_process(persist_service: PersistCollection, db_session: Session) -> None:
    persist_service.persist(collection_result(process("123")))
    persist_service.persist(collection_result(process("456")))
    assert _counts(db_session)["processes"] == 2


def test_additional_identity_reuses_process(
    persist_service: PersistCollection, db_session: Session
) -> None:
    first = process("123")
    persist_service.persist(collection_result(first))
    later = process("123", extra_identities=(identity("XYZ", Source.RHS),))
    persist_service.persist(collection_result(later, round_id=uuid4()))

    counts = _counts(db_session)
    assert counts["processes"] == 1
    assert counts["source_identities"] == 2
    owners = set(
        db_session.execute(text("SELECT process_id FROM source_identities")).scalars()
    )
    assert owners == {first.id}


def test_identity_conflict_rolls_back(
    persist_service: PersistCollection, db_session: Session
) -> None:
    persist_service.persist(collection_result(process("AAA"), round_id=uuid4()))
    persist_service.persist(collection_result(process("BBB"), round_id=uuid4()))
    colliding = process("AAA", extra_identities=(identity("BBB"),))
    colliding_id = uuid4()

    with pytest.raises(IdentityConflictError):
        persist_service.persist(collection_result(colliding, round_id=colliding_id))

    counts = _counts(db_session)
    assert counts["collection_rounds"] == 2
    assert counts["processes"] == 2
    assert counts["source_identities"] == 2
    assert counts["process_observations"] == 2
    exists = db_session.execute(
        text("SELECT COUNT(*) FROM collection_rounds WHERE id = :id"),
        {"id": colliding_id},
    ).scalar_one()
    assert exists == 0


def test_partial_round(persist_service: PersistCollection, db_session: Session) -> None:
    result = collection_result(
        process("123"),
        status=RoundStatus.PARTIAL,
        outcomes=(
            outcome(6, complete=True),
            outcome(8, complete=False, records_received=0, processes_mapped=0, failed_page=2),
        ),
    )
    persist_service.persist(result)

    row = db_session.execute(
        text("SELECT status, unique_processes, records_collected FROM collection_rounds")
    ).one()
    assert row == ("PARTIAL", 1, 1)
    codes = list(
        db_session.execute(
            text(
                "SELECT modality_code, complete FROM collection_modality_outcomes "
                "ORDER BY modality_code"
            )
        )
    )
    assert codes == [(6, True), (8, False)]


def test_zero_opportunities_success(
    persist_service: PersistCollection, db_session: Session
) -> None:
    from collector.domain import RoundMetrics

    result = collection_result(
        outcomes=(outcome(records_received=0, processes_mapped=0),),
        metrics=RoundMetrics(),
        raw_processes=(),
    )
    persist_service.persist(result)

    row = db_session.execute(
        text("SELECT status, unique_processes, records_collected FROM collection_rounds")
    ).one()
    assert row == ("SUCCESS", 0, 0)
    assert _counts(db_session)["processes"] == 0
    assert _counts(db_session)["process_observations"] == 0


def test_persist_outcome_type(persist_service: PersistCollection) -> None:
    outcome_result = persist_service.persist(collection_result(process("123")))
    assert isinstance(outcome_result, PersistOutcome)
    assert outcome_result.created is True
