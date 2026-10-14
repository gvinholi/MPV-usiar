"""Lease persistido (migration 0013) que garante uma única coleta PNCP ativa.

Compartilha a linha ``collection_leases.PNCP_COLLECTION`` com o runner
TypeScript do Worker (``frontend/src/lib/server/collector/lease.ts``): enquanto
um dos dois detiver o lease, o outro pula a rodada. O advisory lock de sessão
anterior não funciona atrás do Hyperdrive (pool em modo transação).

- aquisição atômica: UPDATE condicional (livre ou expirado) que incrementa o
  ``fencing_token``;
- renovação periódica numa thread com conexão própria;
- expiração pelo relógio do banco: um processo morto libera o lease após o TTL;
- liberação condicionada a ``owner_id`` + ``fencing_token``;
- fencing: com ``session_factory``, toda transação de sessão aberta durante o
  lease começa com ``SELECT ... FOR SHARE`` no próprio lease e falha com
  ``CollectionLeaseLostError`` se ele foi perdido. O FOR SHARE faz uma tomada de
  lease esperar as transações em curso, então uma execução antiga nunca grava
  depois que outra assumiu.
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import Connection, Engine, event, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from collector.application.persistence.errors import PersistenceError

PNCP_LEASE = "PNCP_COLLECTION"
DEFAULT_TTL_SECONDS = 120
DEFAULT_HEARTBEAT_SECONDS = 30

_ACQUIRE = text(
    """
    UPDATE collection_leases
    SET owner_id = :owner_id, owner_kind = :owner_kind, fencing_token = fencing_token + 1,
        acquired_at = clock_timestamp(), heartbeat_at = clock_timestamp(),
        expires_at = clock_timestamp() + make_interval(secs => :ttl), released_at = NULL
    WHERE name = :name AND (owner_id IS NULL OR expires_at <= clock_timestamp())
    RETURNING fencing_token
    """
)
_RENEW = text(
    """
    UPDATE collection_leases
    SET heartbeat_at = clock_timestamp(), expires_at = clock_timestamp() + make_interval(secs => :ttl)
    WHERE name = :name AND owner_id = :owner_id AND fencing_token = :token
      AND expires_at > clock_timestamp()
    RETURNING fencing_token
    """
)
_RELEASE = text(
    """
    UPDATE collection_leases
    SET owner_id = NULL, owner_kind = NULL, expires_at = NULL, released_at = clock_timestamp()
    WHERE name = :name AND owner_id = :owner_id AND fencing_token = :token
    RETURNING fencing_token
    """
)
_FENCE = text(
    """
    SELECT fencing_token FROM collection_leases
    WHERE name = :name AND owner_id = :owner_id AND fencing_token = :token
      AND expires_at > clock_timestamp()
    FOR SHARE
    """
)
# Com o lease em mãos, nenhuma outra coleta está viva: rodadas RUNNING são de
# execuções que perderam o lease ou morreram (o runner TS grava RUNNING no início).
_RECOVER_ORPHANS = text(
    """
    UPDATE collection_rounds SET status = 'FAILED', finished_at = clock_timestamp(), errors = errors + 1
    WHERE source = 'PNCP' AND status = 'RUNNING'
    RETURNING id
    """
)


class CollectionLeaseLostError(PersistenceError):
    """O lease da coleta expirou ou foi assumido por outra execução."""


@dataclass(frozen=True)
class CollectionLease:
    name: str
    owner_id: UUID
    owner_kind: str
    fencing_token: int

    @property
    def params(self) -> dict[str, object]:
        return {"name": self.name, "owner_id": self.owner_id, "token": self.fencing_token}


class SqlAlchemyOperationalRunLock:
    def __init__(
        self,
        engine: Engine,
        session_factory: sessionmaker[Session] | None = None,
        *,
        owner_kind: str = "python:cli",
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        heartbeat_seconds: float = DEFAULT_HEARTBEAT_SECONDS,
        lease_name: str = PNCP_LEASE,
    ) -> None:
        if not 0 < heartbeat_seconds < ttl_seconds:
            raise ValueError("heartbeat_seconds deve ser positivo e menor que ttl_seconds")
        self._engine = engine
        self._session_factory = session_factory
        self._owner_kind = owner_kind
        self._ttl = ttl_seconds
        self._heartbeat = heartbeat_seconds
        self._name = lease_name
        self._logger = logging.getLogger(__name__)
        self.lease: CollectionLease | None = None
        self.lost = threading.Event()

    @contextmanager
    def acquire(self) -> Iterator[bool]:
        try:
            connection = self._engine.connect().execution_options(isolation_level="AUTOCOMMIT")
        except SQLAlchemyError as exc:
            raise PersistenceError("falha ao operar lock da coleta") from exc
        with connection:
            lease = self._try_acquire(connection)
            if lease is None:
                yield False
                return
            self.lease = lease
            self.lost.clear()
            self._event("collection_lease_acquired", lease)
            stop = threading.Event()
            heartbeat = threading.Thread(
                target=self._heartbeat_loop, args=(connection, lease, stop),
                name="collection-lease-heartbeat", daemon=True,
            )
            if self._session_factory is not None:
                event.listen(self._session_factory, "after_begin", self._fence_listener)
            try:
                self._recover_orphan_rounds(lease)
                heartbeat.start()
                yield True
            finally:
                stop.set()
                if heartbeat.is_alive():
                    heartbeat.join()
                if self._session_factory is not None:
                    event.remove(self._session_factory, "after_begin", self._fence_listener)
                self._release(connection, lease)
                self.lease = None

    def assert_held(self) -> None:
        """Checkpoint explícito, para trechos que não abrem transação de sessão."""
        lease = self.lease
        if lease is None or self.lost.is_set():
            raise CollectionLeaseLostError("lease da coleta perdido")
        with self._engine.connect() as connection:
            self._fence(connection, lease)
            connection.rollback()

    def _try_acquire(self, connection: Connection) -> CollectionLease | None:
        owner_id = uuid4()
        try:
            token = connection.scalar(
                _ACQUIRE,
                {"name": self._name, "owner_id": owner_id, "owner_kind": self._owner_kind,
                 "ttl": self._ttl},
            )
        except SQLAlchemyError as exc:
            raise PersistenceError("falha ao operar lock da coleta") from exc
        if token is None:
            return None
        return CollectionLease(self._name, owner_id, self._owner_kind, int(token))

    def _heartbeat_loop(self, connection: Connection, lease: CollectionLease, stop: threading.Event) -> None:
        while not stop.wait(self._heartbeat):
            try:
                renewed = connection.scalar(_RENEW, {**lease.params, "ttl": self._ttl})
            except SQLAlchemyError:
                # Falha transitória: tenta de novo no próximo ciclo. Se o TTL
                # vencer antes, o fencing barra as gravações seguintes.
                self._logger.warning('{"event":"collection_lease_renew_failed"}')
                continue
            if renewed is None:
                self.lost.set()
                self._event("collection_lease_lost", lease)
                return

    def _fence_listener(self, session: Session, transaction: object, connection: Connection) -> None:
        lease = self.lease
        if lease is None:
            return
        if self.lost.is_set():
            raise CollectionLeaseLostError("lease da coleta perdido")
        self._fence(connection, lease)

    def _fence(self, connection: Connection, lease: CollectionLease) -> None:
        if connection.scalar(_FENCE, lease.params) is None:
            self.lost.set()
            raise CollectionLeaseLostError("lease da coleta perdido")

    def _recover_orphan_rounds(self, lease: CollectionLease) -> None:
        try:
            with self._engine.begin() as connection:
                self._fence(connection, lease)
                recovered = connection.execute(_RECOVER_ORPHANS).scalars().all()
        except SQLAlchemyError as exc:
            raise PersistenceError("falha ao operar lock da coleta") from exc
        if recovered:
            self._logger.warning(
                json.dumps({"event": "collection_orphan_rounds_failed", "rounds": [str(x) for x in recovered]})
            )

    def _release(self, connection: Connection, lease: CollectionLease) -> None:
        try:
            released = connection.scalar(_RELEASE, lease.params)
        except SQLAlchemyError:
            # O lease expira sozinho pelo TTL; nenhuma outra limpeza é necessária.
            self._logger.error('{"event":"collection_lock_release_failed"}')
            return
        self._event("collection_lease_released" if released is not None else "collection_lease_release_skipped", lease)

    def _event(self, name: str, lease: CollectionLease) -> None:
        self._logger.info(
            json.dumps(
                {"event": name, "lease": lease.name, "owner_id": str(lease.owner_id),
                 "owner_kind": lease.owner_kind, "fencing_token": lease.fencing_token},
                sort_keys=True,
            )
        )
