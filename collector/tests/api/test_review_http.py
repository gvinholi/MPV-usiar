from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from collector.api.app import create_app
from collector.api.security import (
    AuthenticatedPrincipal,
    AuthenticationError,
    AuthenticationUnavailableError,
)
from collector.application.human_review.models import (HumanReview, HumanReviewDecision, HumanReviewReason,
    IdempotencyConflictError, StaleOperationalResolutionError)
from collector.application.human_review_errors import OperationalResolutionNotFoundError

RESOLUTION_ID = UUID("11111111-1111-1111-1111-111111111111")
REVIEW_ID = UUID("22222222-2222-2222-2222-222222222222")
PROCESS_ID = UUID("33333333-3333-3333-3333-333333333333")
PROFILE_ID = UUID("44444444-4444-4444-4444-444444444444")
NOW = datetime(2026, 10, 7, 15, 0, tzinfo=timezone.utc)


class Authenticator:
    def __init__(self, permissions=frozenset({"reviews:write"})): self.permissions = permissions
    def authenticate(self, token):
        if token != "valid-token": raise AuthenticationError("invalid synthetic token")
        return AuthenticatedPrincipal("https://issuer.test.example", "user-123", "Ana Revisora", self.permissions)


class FailingAuthenticator:
    def __init__(self, failure): self.failure = failure
    def authenticate(self, _token): raise self.failure


class ReviewService:
    def __init__(self): self.commands = []; self.failure = None; self.result = None
    def execute(self, command):
        self.commands.append(command)
        if self.failure: raise self.failure
        if self.result: return self.result
        return HumanReview(REVIEW_ID, PROCESS_ID, PROFILE_ID, command, command.allow_stale,
            RESOLUTION_ID, "fingerprint", "CANDIDATE", NOW, NOW, 1)


class Queries:
    pass


def payload(**overrides):
    value = {"operational_resolution_id":str(RESOLUTION_ID), "decision":"SELECTED",
             "reason":"RELEVANT_SCOPE_CONFIRMED", "comment":"Aprovada após análise",
             "idempotency_key":"review-request-1", "allow_stale":False}
    value.update(overrides)
    return value


def client(service=None, authenticator=None):
    return TestClient(create_app(queries=Queries(), review_service=service or ReviewService(),
                                 authenticator=authenticator), raise_server_exceptions=False)


def test_missing_token_is_401_with_challenge():
    response = client(authenticator=Authenticator()).post("/api/v1/reviews", json=payload())
    assert response.status_code == 401 and response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_unconfigured_authentication_fails_closed():
    response = client().post("/api/v1/reviews", json=payload(), headers={"Authorization":"Bearer anything"})
    assert response.status_code == 503 and response.json()["error"]["code"] == "AUTHENTICATION_UNAVAILABLE"


def test_invalid_token_is_401():
    response = client(authenticator=Authenticator()).post("/api/v1/reviews", json=payload(),
        headers={"Authorization":"Bearer invalid"})
    assert response.status_code == 401 and response.headers["WWW-Authenticate"] == "Bearer"


def test_jwks_unavailability_is_503():
    response = client(authenticator=FailingAuthenticator(
        AuthenticationUnavailableError("synthetic provider detail")
    )).post("/api/v1/reviews", json=payload(), headers={"Authorization":"Bearer token"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AUTHENTICATION_UNAVAILABLE"
    assert "provider detail" not in response.text


def test_unexpected_authentication_failure_is_sanitized_500():
    response = client(authenticator=FailingAuthenticator(
        RuntimeError("secret internal authenticator detail")
    )).post("/api/v1/reviews", json=payload(), headers={"Authorization":"Bearer token"})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "secret internal" not in response.text


def test_missing_permission_is_403():
    response = client(authenticator=Authenticator(frozenset())).post("/api/v1/reviews", json=payload(),
        headers={"Authorization":"Bearer valid-token"})
    assert response.status_code == 403 and response.json()["error"]["code"] == "FORBIDDEN"


def test_authorized_reviewer_is_derived_only_from_token():
    service = ReviewService()
    response = client(service, Authenticator()).post("/api/v1/reviews", json=payload(),
        headers={"Authorization":"Bearer valid-token"})
    assert response.status_code == 201
    command = service.commands[0]
    assert command.reviewer.reviewer_id == "oidc:27:https://issuer.test.exampleuser-123"
    assert command.reviewer.display_name == "Ana Revisora"
    assert response.json()["reviewer_id"] == command.reviewer.reviewer_id
    assert response.json()["decision"] == "SELECTED"


@pytest.mark.parametrize("field", ["reviewer_id", "reviewer", "permissions", "display_name"])
def test_caller_cannot_supply_identity(field):
    response = client(authenticator=Authenticator()).post("/api/v1/reviews", json=payload(**{field:"attacker"}),
        headers={"Authorization":"Bearer valid-token"})
    assert response.status_code == 422 and response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("changes", [
    {"decision":"CONFIRMED"}, {"reason":"NOT_A_REASON"},
    {"decision":"SELECTED", "reason":"OUT_OF_SCOPE"},
    {"decision":"DISCARDED", "reason":"OTHER", "comment":None},
])
def test_invalid_decision_or_reason_is_422(changes):
    response = client(authenticator=Authenticator()).post("/api/v1/reviews", json=payload(**changes),
        headers={"Authorization":"Bearer valid-token"})
    assert response.status_code == 422 and response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_identical_retry_returns_same_review():
    service = ReviewService(); api = client(service, Authenticator()); headers={"Authorization":"Bearer valid-token"}
    first = api.post("/api/v1/reviews", json=payload(), headers=headers)
    second = api.post("/api/v1/reviews", json=payload(), headers=headers)
    assert first.status_code == second.status_code == 201
    assert first.json()["review_id"] == second.json()["review_id"]
    assert service.commands[0] == service.commands[1]


@pytest.mark.parametrize(("failure","status","code"), [
    (IdempotencyConflictError(),409,"IDEMPOTENCY_CONFLICT"),
    (StaleOperationalResolutionError(RESOLUTION_ID, UUID("55555555-5555-5555-5555-555555555555")),409,"STALE_OPERATIONAL_RESOLUTION"),
    (OperationalResolutionNotFoundError(str(RESOLUTION_ID)),404,"OPERATIONAL_RESOLUTION_NOT_FOUND"),
])
def test_domain_errors_are_mapped(failure, status, code):
    service=ReviewService(); service.failure=failure
    response=client(service,Authenticator()).post("/api/v1/reviews",json=payload(),headers={"Authorization":"Bearer valid-token"})
    assert response.status_code == status and response.json()["error"]["code"] == code


def test_allow_stale_reaches_existing_command_contract():
    service=ReviewService()
    response=client(service,Authenticator()).post("/api/v1/reviews",json=payload(allow_stale=True),headers={"Authorization":"Bearer valid-token"})
    assert response.status_code == 201 and service.commands[0].allow_stale is True
    assert response.json()["was_stale_at_decision"] is True


def test_unexpected_service_value_error_is_not_misreported_as_422():
    service = ReviewService()
    service.failure = ValueError("secret unexpected service detail")
    response = client(service, Authenticator()).post(
        "/api/v1/reviews", json=payload(), headers={"Authorization":"Bearer valid-token"}
    )
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "secret unexpected" not in response.text


def test_token_is_not_logged(caplog):
    secret="valid-token"
    with caplog.at_level("INFO",logger="collector.api.app"):
        response=client(authenticator=Authenticator()).post("/api/v1/reviews",json=payload(),headers={"Authorization":f"Bearer {secret}"})
    assert response.status_code == 201
    assert secret not in "\n".join(record.getMessage() for record in caplog.records)


def test_health_remains_public():
    assert client(authenticator=Authenticator()).get("/health").status_code == 200


def test_dashboard_read_does_not_grant_review_write():
    response = client(authenticator=Authenticator(frozenset({"dashboard:read"}))).post(
        "/api/v1/reviews", json=payload(), headers={"Authorization": "Bearer valid-token"}
    )
    assert response.status_code == 403


def test_both_permissions_preserve_review_write():
    response = client(authenticator=Authenticator(
        frozenset({"dashboard:read", "reviews:write"})
    )).post("/api/v1/reviews", json=payload(), headers={"Authorization": "Bearer valid-token"})
    assert response.status_code == 201


def test_openapi_documents_jwt_permission_and_responses_without_oauth_flow():
    document = client(authenticator=Authenticator()).get("/openapi.json").json()
    scheme = document["components"]["securitySchemes"]["OIDC Bearer"]
    operation = document["paths"]["/api/v1/reviews"]["post"]
    assert scheme["type"] == "http"
    assert scheme["scheme"] == "bearer"
    assert scheme["bearerFormat"] == "JWT"
    assert "flows" not in scheme
    assert "reviews:write" in scheme["description"]
    assert "reviews:write" in operation["description"]
    assert operation["security"] == [{"OIDC Bearer": []}]
    assert {"201", "401", "403", "404", "409", "422", "500", "503"} <= set(operation["responses"])
    assert "security" not in document["paths"]["/health"]["get"]
