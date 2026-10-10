from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from collector.api.app import create_app
from collector.api.security import (AuthenticatedPrincipal, AuthenticationError,
    AuthenticationUnavailableError)
from collector.api.settings import ApiSettings
from collector.application.human_review.models import HumanReviewStatus
from collector.application.read_model.errors import (AmbiguousProfileError, CollectionRoundNotFoundError,
    OpportunityNotFoundError, ProfileNotFoundError)
from collector.application.read_model.filters import TimeRange
from collector.application.read_model.models import (CollectionRoundDetail, CollectionRoundListItem, CurrentSnapshot,
    DashboardSummary, OpportunityCounters, OpportunityDetail, OpportunityListItem, PeriodActivity, PilotFunnel)
from collector.application.read_model.pagination import Page

NOW = datetime(2026, 10, 6, 19, 0, tzinfo=timezone.utc)
PROCESS_ID = UUID("11111111-1111-1111-1111-111111111111")
PROFILE_ID = UUID("22222222-2222-2222-2222-222222222222")
ROUND_ID = UUID("33333333-3333-3333-3333-333333333333")


def item():
    return OpportunityListItem(PROCESS_ID, "PNCP", "00509968000148/2026/3341",
        "Manutenção preventiva de climatização – São Paulo", "Órgão Público", None, "São Paulo", "SP", None,
        Decimal("125000.50"), NOW, None, None, None, "CANDIDATE", "reason", NOW,
        HumanReviewStatus.UNREVIEWED, None, None, None, 0, False, False, NOW)


def detail():
    return OpportunityDetail(item(), None, (), None, None, None, None, None, None,
                             OpportunityCounters(0, 0, 0, 0, 0))


def summary():
    return DashboardSummary(PROFILE_ID, TimeRange(NOW, None), CurrentSnapshot(*([0] * 12)),
        PeriodActivity(*([0] * 10)), PilotFunnel(*([0] * 12)), ())


def round_item(status="SUCCESS"):
    return CollectionRoundListItem(ROUND_ID, "PNCP", NOW, NOW, status, 0, 0, 0, 0, 0, (), ())


class FakeQueries:
    def __init__(self): self.calls = []; self.failure = None
    def _check(self):
        if self.failure: raise self.failure
    def dashboard_summary(self, scope, period): self._check(); self.calls.append(("summary", scope, period)); return summary()
    def list_opportunities(self, scope, filters, pagination, sort):
        self._check(); self.calls.append(("list", scope, filters, pagination, sort)); return Page((item(),), pagination.page, pagination.page_size, 1)
    def get_opportunity(self, process_id, scope): self._check(); return detail()
    def get_opportunity_by_source_identity(self, source, official_id, scope):
        self._check(); self.calls.append(("source", source, official_id, scope)); return detail()
    def documents(self, process_id, pagination): return Page((), pagination.page, pagination.page_size, 0)
    def document_evidence(self, process_id, scope, pagination): return Page((), pagination.page, pagination.page_size, 0)
    def timeline(self, process_id, scope, pagination): return Page((), pagination.page, pagination.page_size, 0)
    def review_queue(self, scope, queue, filters=None, pagination=None, sort=None): return Page((), pagination.page, pagination.page_size, 0)
    def collection_rounds(self, period, pagination, source): return Page((round_item(),), pagination.page, pagination.page_size, 1)
    def collection_round_detail(self, round_id): self._check(); return CollectionRoundDetail(round_item(), 0, 0, 0, 0, 0, 0)


class Session:
    def __init__(self, fails=False): self.fails = fails
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def execute(self, _statement):
        if self.fails: raise RuntimeError("postgresql://secret-user:super-secret@internal-host/db SELECT secret")


class Authenticator:
    def __init__(self, permissions=frozenset({"dashboard:read"}), failure=None):
        self.permissions = permissions
        self.failure = failure

    def authenticate(self, token):
        if self.failure:
            raise self.failure
        if token != "valid-token":
            raise AuthenticationError("invalid synthetic token")
        return AuthenticatedPrincipal(
            "https://issuer.test.example", "dashboard-user", "Dashboard User", self.permissions
        )


def api_client(fake, *, authenticator=None, session_factory=None, settings=None):
    value = TestClient(create_app(
        queries=fake,
        session_factory=session_factory,
        settings=settings or ApiSettings(auth_mode="oidc"),
        authenticator=authenticator or Authenticator(),
    ), raise_server_exceptions=False)
    value.headers["Authorization"] = "Bearer valid-token"
    return value


@pytest.fixture
def fake(): return FakeQueries()
@pytest.fixture
def client(fake): return api_client(fake, session_factory=lambda: Session())


def test_health_ready_and_openapi(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"status": "ready"}
    document = client.get("/openapi.json").json()
    paths = document["paths"]
    assert "/api/v1/opportunities" in paths
    money = document["components"]["schemas"]["OpportunityListItemResponse"]["properties"]["estimated_value"]
    assert {part.get("type") for part in money["anyOf"]} == {"string", "null"}


def test_list_contract_decimal_datetime_uuid_enum_null_unicode(client):
    body = client.get("/api/v1/opportunities", params={"profile_id": str(PROFILE_ID)}).json()
    result = body["items"][0]
    assert result["estimated_value"] == "125000.50"
    assert result["publication_at"] == "2026-10-06T19:00:00Z"
    assert result["process_id"] == str(PROCESS_ID)
    assert result["human_review_status"] == "UNREVIEWED"
    assert result["human_decision"] is None
    assert result["description_preview"] == "Manutenção preventiva de climatização – São Paulo"
    assert body["pagination"] == {"page": 1, "page_size": 25, "total_items": 1, "total_pages": 1}


def test_filters_reach_application(fake):
    client = api_client(fake)
    params = {"profile_code":"USIAR", "operational_state":"CANDIDATE", "human_review_status":"UNREVIEWED",
        "human_decision":"SELECTED", "source":"PNCP", "uf":"sp", "municipality":"São Paulo", "modality":"Pregão",
        "search":"climatização", "has_documents":"true", "has_text":"false", "has_document_screening":"true",
        "publication_from":"2026-10-01T00:00:00Z", "publication_to":"2026-11-01T00:00:00Z",
        "proposal_deadline_from":"2026-10-02T00:00:00Z", "captured_from":"2026-10-03T00:00:00Z",
        "review_queue":"NEEDS_REVIEW", "page":2, "page_size":10, "sort":"estimated_value", "direction":"ASC"}
    assert client.get("/api/v1/opportunities", params=params).status_code == 200
    _, scope, filters, pagination, sort = fake.calls[-1]
    assert scope.profile_code == "USIAR" and filters.uf == "SP" and filters.has_documents is True
    assert pagination.page == 2 and sort.field.value == "estimated_value" and sort.direction.value == "ASC"


def test_detail_lookup_and_paginated_endpoints(client, fake):
    assert client.get(f"/api/v1/opportunities/{PROCESS_ID}", params={"profile_id":str(PROFILE_ID)}).status_code == 200
    official = "00509968000148/2026/3341"
    assert client.get("/api/v1/opportunities/by-source", params={"source":"PNCP", "official_id":official, "profile_id":str(PROFILE_ID)}).status_code == 200
    assert fake.calls[-1][2] == official
    for suffix in ("documents", "document-evidence", "timeline"):
        response = client.get(f"/api/v1/opportunities/{PROCESS_ID}/{suffix}", params={"profile_id":str(PROFILE_ID)})
        assert response.status_code == 200 and response.json()["pagination"]["total_items"] == 0
    assert client.get("/api/v1/review-queue", params={"profile_id":str(PROFILE_ID)}).status_code == 200
    assert client.get("/api/v1/collection-rounds").json()["items"][0]["status"] == "SUCCESS"
    assert client.get(f"/api/v1/collection-rounds/{ROUND_ID}").status_code == 200


@pytest.mark.parametrize("params", [{"page":0}, {"page_size":0}, {"page_size":101}, {"sort":"DROP TABLE processes"}, {"direction":"SIDEWAYS"}, {"profile_id":"bad"}, {"publication_from":"bad"}])
def test_validation_is_normalized(client, params):
    response = client.get("/api/v1/opportunities", params=params)
    assert response.status_code == 422 and response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_inverted_or_naive_range_is_validation(client):
    for params in ({"profile_id":str(PROFILE_ID), "publication_from":"2026-11-01T00:00:00Z", "publication_to":"2026-10-01T00:00:00Z"},
                   {"profile_id":str(PROFILE_ID), "publication_from":"2026-10-01T00:00:00"}):
        assert client.get("/api/v1/opportunities", params=params).status_code == 422


def test_explicit_source_contract_validation_remains_422(client):
    by_source = client.get("/api/v1/opportunities/by-source", params={
        "source":"INVALID", "official_id":" ", "profile_id":str(PROFILE_ID),
    })
    rounds = client.get("/api/v1/collection-rounds", params={"source":"INVALID"})
    assert by_source.status_code == 422
    assert rounds.status_code == 422


@pytest.mark.parametrize(("failure","status","code"), [(OpportunityNotFoundError(),404,"OPPORTUNITY_NOT_FOUND"),
    (ProfileNotFoundError(),404,"PROFILE_NOT_FOUND"), (AmbiguousProfileError(),409,"AMBIGUOUS_PROFILE"),
    (RuntimeError("secret SQL C:/private"),500,"INTERNAL_ERROR")])
def test_safe_errors(fake, failure, status, code):
    fake.failure = failure
    response = api_client(fake).get(f"/api/v1/opportunities/{PROCESS_ID}", params={"profile_id":str(PROFILE_ID)})
    assert response.status_code == status and response.json()["error"]["code"] == code
    assert "secret" not in response.text and "Traceback" not in response.text


def test_round_not_found(fake):
    fake.failure = CollectionRoundNotFoundError()
    response = api_client(fake).get(f"/api/v1/collection-rounds/{ROUND_ID}")
    assert response.status_code == 404 and response.json()["error"]["code"] == "COLLECTION_ROUND_NOT_FOUND"


def test_ready_failure_does_not_leak(fake):
    response = api_client(fake, session_factory=lambda:Session(True)).get("/ready")
    assert response.status_code == 503
    for secret in ("secret-user", "super-secret", "internal-host", "SELECT"): assert secret not in response.text


def test_request_id_and_cors(fake):
    app = create_app(queries=fake, settings=ApiSettings(auth_mode="oidc", cors_origins=("https://dashboard.example",)), authenticator=Authenticator())
    client = TestClient(app)
    assert UUID(client.get("/health").headers["X-Request-ID"])
    assert client.get("/health", headers={"X-Request-ID":"valid-123"}).headers["X-Request-ID"] == "valid-123"
    assert client.get("/health", headers={"X-Request-ID":"x"*129}).headers["X-Request-ID"] != "x"*129
    assert client.get("/health", headers={"Origin":"https://dashboard.example"}).headers["access-control-allow-origin"] == "https://dashboard.example"
    assert "access-control-allow-origin" not in client.get("/health", headers={"Origin":"https://evil.example"}).headers
    default = TestClient(create_app(queries=fake, settings=ApiSettings(auth_mode="oidc"), authenticator=Authenticator())).get("/health", headers={"Origin":"https://dashboard.example"})
    assert "access-control-allow-origin" not in default.headers


def test_error_always_has_request_id_and_logging_is_safe(fake, caplog):
    fake.failure = RuntimeError("postgresql://secret-user:super-secret@internal-host/db Authorization Cookie")
    with caplog.at_level("INFO", logger="collector.api.app"):
        response = api_client(fake).get(
            f"/api/v1/opportunities/{PROCESS_ID}", params={"profile_id":str(PROFILE_ID)},
            headers={"X-Request-ID":"request-safe"})
    assert response.status_code == 500 and response.headers["X-Request-ID"] == "request-safe"
    http_logs = [record.message for record in caplog.records if record.levelname == "INFO"]
    assert any("request_id=request-safe" in message and "method=GET" in message and "status=500" in message for message in http_logs)
    assert all("Authorization" not in message and "Cookie" not in message and "super-secret" not in message for message in http_logs)


def test_detail_payload_has_no_blob_text_or_storage_path(client):
    body = client.get(f"/api/v1/opportunities/{PROCESS_ID}", params={"profile_id":str(PROFILE_ID)}).json()
    encoded = str(body).lower()
    for forbidden in ("storage_path", "filesystem", "pdf_bytes", "zip_bytes", "page_text"):
        assert forbidden not in encoded


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_write_methods_are_not_allowed(client, method):
    assert getattr(client, method)("/api/v1/opportunities").status_code == 405


OPERATIONAL_GETS = (
    ("/ready", {}),
    ("/api/v1/dashboard/summary", {"profile_id": str(PROFILE_ID)}),
    ("/api/v1/opportunities", {"profile_id": str(PROFILE_ID)}),
    ("/api/v1/opportunities/by-source", {
        "source": "PNCP", "official_id": "00509968000148/2026/3341", "profile_id": str(PROFILE_ID),
    }),
    (f"/api/v1/opportunities/{PROCESS_ID}", {"profile_id": str(PROFILE_ID)}),
    (f"/api/v1/opportunities/{PROCESS_ID}/documents", {}),
    (f"/api/v1/opportunities/{PROCESS_ID}/document-evidence", {"profile_id": str(PROFILE_ID)}),
    (f"/api/v1/opportunities/{PROCESS_ID}/timeline", {"profile_id": str(PROFILE_ID)}),
    ("/api/v1/review-queue", {"profile_id": str(PROFILE_ID)}),
    ("/api/v1/collection-rounds", {}),
    (f"/api/v1/collection-rounds/{ROUND_ID}", {}),
)


@pytest.mark.parametrize(("path", "params"), OPERATIONAL_GETS)
def test_every_operational_get_requires_token(fake, path, params):
    response = TestClient(create_app(queries=fake, session_factory=lambda: Session(),
        settings=ApiSettings(auth_mode="oidc"), authenticator=Authenticator()), raise_server_exceptions=False).get(path, params=params)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.parametrize(("path", "params"), OPERATIONAL_GETS)
def test_reviews_write_does_not_grant_dashboard_read(fake, path, params):
    response = api_client(fake, authenticator=Authenticator(frozenset({"reviews:write"})),
                          session_factory=lambda: Session()).get(path, params=params)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_invalid_token_is_401_for_operational_get(fake):
    response = api_client(fake).get("/api/v1/collection-rounds",
                                    headers={"Authorization": "Bearer invalid-token"})
    assert response.status_code == 401


def test_principal_with_both_permissions_can_read(fake):
    response = api_client(fake, authenticator=Authenticator(
        frozenset({"dashboard:read", "reviews:write"})
    )).get("/api/v1/collection-rounds")
    assert response.status_code == 200


@pytest.mark.parametrize(("failure", "status", "code"), [
    (AuthenticationUnavailableError("provider secret"), 503, "AUTHENTICATION_UNAVAILABLE"),
    (RuntimeError("internal authenticator secret"), 500, "INTERNAL_ERROR"),
])
def test_operational_get_authentication_failures_are_sanitized(fake, failure, status, code):
    response = api_client(fake, authenticator=Authenticator(failure=failure)).get(
        "/api/v1/collection-rounds"
    )
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert "secret" not in response.text


def test_operational_get_token_is_not_logged(fake, caplog):
    secret = "valid-token"
    with caplog.at_level("INFO", logger="collector.api.app"):
        response = api_client(fake).get(
            "/api/v1/collection-rounds", headers={"Authorization": f"Bearer {secret}"}
        )
    assert response.status_code == 200
    assert secret not in "\n".join(record.getMessage() for record in caplog.records)


def test_openapi_documents_dashboard_permission_on_all_operational_gets(fake):
    document = api_client(fake).get("/openapi.json").json()
    protected_paths = {path.replace(str(PROCESS_ID), "{process_id}").replace(str(ROUND_ID), "{round_id}")
                       for path, _params in OPERATIONAL_GETS}
    actual_operational_gets = {
        path for path, operations in document["paths"].items()
        if "get" in operations and (path.startswith("/api/v1/") or path == "/ready")
    }
    assert actual_operational_gets == protected_paths
    for path in protected_paths:
        operation = document["paths"][path]["get"]
        assert operation["security"] == [{"OIDC Bearer": []}]
        assert "dashboard:read" in operation["description"]
        assert {"401", "403", "500", "503"} <= set(operation["responses"])
    assert "security" not in document["paths"]["/health"]["get"]


def test_documentation_is_disabled_by_default_in_production_and_can_be_enabled(fake):
    production = TestClient(create_app(queries=fake, settings=ApiSettings(auth_mode="oidc", environment="production"), authenticator=Authenticator()))
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert production.get(path).status_code == 404
    enabled = TestClient(create_app(
        queries=fake, settings=ApiSettings(auth_mode="oidc", environment="production", api_docs_enabled=True), authenticator=Authenticator()
    ))
    assert enabled.get("/openapi.json").status_code == 200


def test_protected_get_fails_closed_when_oidc_is_not_configured(fake):
    with pytest.raises(ValueError, match="OIDC configuration is incomplete"):
        create_app(queries=fake, settings=ApiSettings(auth_mode="oidc"))
