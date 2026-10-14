"""Cross-process exclusion uses a real PostgreSQL advisory lock."""

import pytest

from collector.infra.database import SqlAlchemyOperationalRunLock

pytestmark = pytest.mark.postgres


def test_postgres_lock_is_non_blocking_and_released_after_scope(migrated_engine):
    first = SqlAlchemyOperationalRunLock(migrated_engine)
    second = SqlAlchemyOperationalRunLock(migrated_engine)

    with first.acquire() as first_acquired:
        assert first_acquired is True
        with second.acquire() as second_acquired:
            assert second_acquired is False

    with second.acquire() as acquired_after_release:
        assert acquired_after_release is True
