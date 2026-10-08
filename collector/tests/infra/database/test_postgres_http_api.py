"""Real HTTP -> DashboardQueries -> PostgreSQL smoke contracts."""
from datetime import datetime, timezone
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from collector.api.app import create_app
from collector.api.security import AuthenticatedPrincipal
from collector.application.read_model.service import DashboardQueries
from collector.infra.database.read_model_store import SqlAlchemyReadModelStore

pytestmark = pytest.mark.postgres


class DashboardAuthenticator:
    def authenticate(self, token):
        assert token == "postgres-test-token"
        return AuthenticatedPrincipal(
            "https://issuer.test.example", "postgres-reader", None, frozenset({"dashboard:read"})
        )

def test_ready_and_zero_record_round_statuses_over_real_postgres(migrated_engine, db_session):
    now = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)
    success_id, failed_id = uuid4(), uuid4()
    statement = text("""
        INSERT INTO collection_rounds
        (id, source, started_at, finished_at, status, pages_expected, pages_processed,
         pages_with_error, records_collected, unique_processes, candidates, selected,
         pending, discarded, documents_found, errors, created_at)
        VALUES (:id, 'PNCP', :now, :now, :status, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, :now)
    """)
    with migrated_engine.begin() as connection:
        connection.execute(statement, {"id": success_id, "now": now, "status": "SUCCESS"})
        connection.execute(statement, {"id": failed_id, "now": now, "status": "FAILED"})
    factory = sessionmaker(bind=migrated_engine, autoflush=False, expire_on_commit=False)
    client = TestClient(create_app(
        queries=DashboardQueries(SqlAlchemyReadModelStore(factory)), session_factory=factory,
        authenticator=DashboardAuthenticator(),
    ), headers={"Authorization": "Bearer postgres-test-token"})
    assert client.get("/ready").json() == {"status": "ready"}
    response = client.get("/api/v1/collection-rounds", params={"page_size": 100})
    assert response.status_code == 200
    statuses = {item["round_id"]: item["status"] for item in response.json()["items"]}
    assert statuses[str(success_id)] == "SUCCESS"
    assert statuses[str(failed_id)] == "FAILED"
