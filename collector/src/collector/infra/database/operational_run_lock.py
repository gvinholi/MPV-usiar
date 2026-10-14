"""Session-level PostgreSQL advisory lock for the PNCP operational runner."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from collector.application.persistence.errors import PersistenceError

_LOCK_NAMESPACE = 0x55534941  # ASCII "USIA", stable across processes.
_PNCP_OPERATION = 1


class SqlAlchemyOperationalRunLock:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._logger = logging.getLogger(__name__)

    @contextmanager
    def acquire(self) -> Iterator[bool]:
        try:
            connection = self._engine.connect()
        except SQLAlchemyError as exc:
            raise PersistenceError("falha ao operar lock da coleta") from exc
        with connection:
            try:
                acquired = bool(
                    connection.scalar(
                        text("SELECT pg_try_advisory_lock(:namespace, :operation)"),
                        {"namespace": _LOCK_NAMESPACE, "operation": _PNCP_OPERATION},
                    )
                )
            except SQLAlchemyError as exc:
                raise PersistenceError("falha ao operar lock da coleta") from exc
            try:
                yield acquired
            finally:
                if acquired:
                    try:
                        connection.scalar(
                            text("SELECT pg_advisory_unlock(:namespace, :operation)"),
                            {
                                "namespace": _LOCK_NAMESPACE,
                                "operation": _PNCP_OPERATION,
                            },
                        )
                    except SQLAlchemyError:
                        # Invalidating closes the physical session and releases its lock.
                        connection.invalidate()
                        self._logger.error('{"event":"collection_lock_release_failed"}')
