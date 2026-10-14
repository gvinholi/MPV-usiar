"""Lease persistido da coleta (migration 0013) contra PostgreSQL real.

Cobre exclusão mútua, corrida de aquisição, renovação, expiração, perda do
lease durante a execução, fencing e recuperação de rodadas órfãs. A mesma linha
é usada pelo runner TypeScript (ver frontend/src/lib/server/collector/lease.ts).
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from psycopg import errors
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from collector.infra.database import (
    CollectionLeaseLostError,
    SqlAlchemyOperationalRunLock,
)
from collector.infra.database.operational_run_lock import PNCP_LEASE

pytestmark = pytest.mark.postgres


@pytest.fixture(autouse=True)
def free_lease(admin_engine):
    def reset() -> None:
        with admin_engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE collection_leases SET owner_id = NULL, owner_kind = NULL, expires_at = NULL "
                    "WHERE name = :name"
                ),
                {"name": PNCP_LEASE},
            )
            connection.execute(text("TRUNCATE collection_rounds CASCADE"))

    reset()
    yield
    reset()


def _lease_row(engine):
    with engine.connect() as connection:
        return connection.execute(
            text(
                "SELECT owner_id, owner_kind, fencing_token, expires_at, heartbeat_at, released_at "
                "FROM collection_leases WHERE name = :name"
            ),
            {"name": PNCP_LEASE},
        ).one()


def _expire_now(admin_engine) -> None:
    """Simula TTL vencido (processo travado/sem heartbeat) sem esperar o relógio."""
    with admin_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE collection_leases SET heartbeat_at = clock_timestamp() - interval '10 minutes', "
                "expires_at = clock_timestamp() - interval '1 second' WHERE name = :name"
            ),
            {"name": PNCP_LEASE},
        )


def _round(connection, status: str = "RUNNING"):
    round_id = uuid4()
    connection.execute(
        text(
            "INSERT INTO collection_rounds (id, source, started_at, status, pages_expected, pages_processed, "
            "pages_with_error, records_collected, unique_processes, candidates, selected, pending, discarded, "
            "documents_found, errors, created_at) VALUES (:id, 'PNCP', :now, :status, 0,0,0,0,0,0,0,0,0,0,0, :now)"
        ),
        {"id": round_id, "now": datetime.now(UTC), "status": status},
    )
    return round_id


def test_lease_is_exclusive_and_released_after_scope(migrated_engine):
    first = SqlAlchemyOperationalRunLock(migrated_engine)
    second = SqlAlchemyOperationalRunLock(migrated_engine)

    with first.acquire() as first_acquired:
        assert first_acquired is True
        row = _lease_row(migrated_engine)
        assert row.owner_id == first.lease.owner_id and row.owner_kind == "python:cli"
        with second.acquire() as second_acquired:
            assert second_acquired is False

    released = _lease_row(migrated_engine)
    assert released.owner_id is None and released.released_at is not None
    with second.acquire() as acquired_after_release:
        assert acquired_after_release is True
        assert second.lease.fencing_token == row.fencing_token + 1


def test_concurrent_acquisition_has_exactly_one_winner(migrated_engine):
    barrier = threading.Barrier(8)
    results: list[bool] = []
    hold = threading.Event()

    def contender() -> None:
        lock = SqlAlchemyOperationalRunLock(migrated_engine)
        barrier.wait()
        with lock.acquire() as acquired:
            results.append(acquired)
            if acquired:
                hold.wait(2)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(contender) for _ in range(8)]
        while len(results) < 8:
            time.sleep(0.05)
        hold.set()
        for future in futures:
            future.result()
    assert sorted(results) == [False] * 7 + [True]


def test_heartbeat_renews_before_expiry(migrated_engine):
    lock = SqlAlchemyOperationalRunLock(migrated_engine, ttl_seconds=2, heartbeat_seconds=0.4)
    with lock.acquire() as acquired:
        assert acquired
        initial = _lease_row(migrated_engine)
        time.sleep(3)  # > TTL: sem renovação o lease teria vencido
        renewed = _lease_row(migrated_engine)
        assert renewed.expires_at > initial.expires_at
        assert renewed.heartbeat_at > initial.heartbeat_at
        assert not lock.lost.is_set()
        with SqlAlchemyOperationalRunLock(migrated_engine).acquire() as contended:
            assert contended is False
        lock.assert_held()


def test_expired_lease_is_recovered_and_orphan_rounds_closed(migrated_engine, admin_engine):
    crashed = SqlAlchemyOperationalRunLock(migrated_engine)
    context = crashed.acquire()
    assert context.__enter__() is True  # processo "morre" sem sair do contexto
    stale_token = crashed.lease.fencing_token
    with admin_engine.begin() as connection:
        orphan = _round(connection, "RUNNING")
        finished = _round(connection, "SUCCESS")
    try:
        with SqlAlchemyOperationalRunLock(migrated_engine).acquire() as contended:
            assert contended is False  # ainda dentro do TTL
        _expire_now(admin_engine)
        successor = SqlAlchemyOperationalRunLock(migrated_engine)
        with successor.acquire() as acquired:
            assert acquired is True
            assert successor.lease.fencing_token == stale_token + 1
            with admin_engine.connect() as connection:
                statuses = dict(connection.execute(text("SELECT id, status FROM collection_rounds")).all())
            assert statuses == {orphan: "FAILED", finished: "SUCCESS"}
    finally:
        # O antigo dono tenta liberar: condicionado ao token, não afeta ninguém.
        context.__exit__(None, None, None)
    assert _lease_row(migrated_engine).fencing_token == stale_token + 1


def test_lost_lease_blocks_writes_of_the_old_owner(migrated_engine, admin_engine):
    factory = sessionmaker(bind=migrated_engine, autoflush=False, expire_on_commit=False)
    old = SqlAlchemyOperationalRunLock(migrated_engine, factory)
    with old.acquire() as acquired:
        assert acquired
        with factory.begin() as session:  # fenced: lease válido
            _round(session.connection(), "SUCCESS")
        _expire_now(admin_engine)
        with SqlAlchemyOperationalRunLock(migrated_engine).acquire() as successor:
            assert successor is True
            with pytest.raises(CollectionLeaseLostError), factory.begin() as session:
                _round(session.connection(), "SUCCESS")
            assert old.lost.is_set()
            with pytest.raises(CollectionLeaseLostError):
                old.assert_held()
    with admin_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM collection_rounds")) == 1


def test_heartbeat_detects_loss(migrated_engine, admin_engine):
    lock = SqlAlchemyOperationalRunLock(migrated_engine, ttl_seconds=5, heartbeat_seconds=0.3)
    with lock.acquire() as acquired:
        assert acquired
        _expire_now(admin_engine)
        with SqlAlchemyOperationalRunLock(migrated_engine).acquire() as successor:
            assert successor is True
            assert lock.lost.wait(3)


def test_takeover_waits_for_in_flight_fenced_transaction(migrated_engine, admin_engine):
    """Fencing: a nova execução só assume depois do COMMIT da transação antiga."""
    factory = sessionmaker(bind=migrated_engine, autoflush=False, expire_on_commit=False)
    old = SqlAlchemyOperationalRunLock(migrated_engine, factory)
    took_over = threading.Event()
    with old.acquire() as acquired:
        assert acquired
        session = factory()
        session.begin()
        _round(session.connection(), "SUCCESS")  # FOR SHARE no lease já tomado
        _expire_now_without_waiting = threading.Thread(target=_expire_now, args=(admin_engine,))
        _expire_now_without_waiting.start()
        time.sleep(0.5)
        # O próprio UPDATE de expiração espera o FOR SHARE: nada muda no meio da transação.
        assert _expire_now_without_waiting.is_alive()

        def successor() -> None:
            with SqlAlchemyOperationalRunLock(migrated_engine).acquire() as ok:
                if ok:
                    took_over.set()

        session.commit()
        session.close()
        _expire_now_without_waiting.join(5)
        thread = threading.Thread(target=successor)
        thread.start()
        thread.join(5)
    assert took_over.is_set()
    with admin_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM collection_rounds")) == 1


def test_release_and_renew_require_owner_and_token(migrated_engine):
    lock = SqlAlchemyOperationalRunLock(migrated_engine)
    with lock.acquire():
        token = lock.lease.fencing_token
        with migrated_engine.begin() as connection:
            for statement in (
                (
                    "UPDATE collection_leases SET owner_id = NULL, owner_kind = NULL, expires_at = NULL "
                    "WHERE name = :name AND owner_id = :other AND fencing_token = :token"
                ),
                (
                    "UPDATE collection_leases SET owner_id = NULL, owner_kind = NULL, expires_at = NULL "
                    "WHERE name = :name AND owner_id = :owner AND fencing_token = :stale"
                ),
            ):
                result = connection.execute(
                    text(statement),
                    {"name": PNCP_LEASE, "other": uuid4(), "owner": lock.lease.owner_id,
                     "token": token, "stale": token - 1},
                )
                assert result.rowcount == 0
        assert _lease_row(migrated_engine).owner_id == lock.lease.owner_id


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE collection_leases SET fencing_token = 0",
        (
            "UPDATE collection_leases SET owner_id = gen_random_uuid(), owner_kind = 'x', "
            "acquired_at = now(), heartbeat_at = now(), expires_at = now() + interval '1 minute'"
        ),
    ],
)
def test_fencing_token_cannot_be_rewound_or_reused(migrated_engine, statement):
    with SqlAlchemyOperationalRunLock(migrated_engine).acquire():
        pass  # token > 0
    with migrated_engine.connect() as connection:
        with pytest.raises(DBAPIError) as caught:
            connection.execute(text(statement))
        assert isinstance(caught.value.orig, errors.CheckViolation)
        connection.rollback()


def test_invalid_heartbeat_configuration_is_rejected(migrated_engine):
    with pytest.raises(ValueError):
        SqlAlchemyOperationalRunLock(migrated_engine, ttl_seconds=10, heartbeat_seconds=10)
