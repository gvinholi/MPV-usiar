from datetime import UTC, datetime, timedelta

import pytest
from collector.api.app import create_app
from collector.api.security import AuthenticatedPrincipal
from collector.api.settings import ApiSettings
from collector.application.internal_auth import (
    AuthenticationCapacityError,
    AuthenticationRateLimitedError,
    CreatedSession,
    InvalidCredentialsError,
    InvalidCsrfTokenError,
    InvalidInternalSessionError,
)
from fastapi.testclient import TestClient

NOW = datetime(2026, 10, 9, 17, tzinfo=UTC)


class Queries:
    pass


class Authenticator:
    def authenticate(self, _token):
        return AuthenticatedPrincipal("issuer", "subject", None, frozenset())


class LoginService:
    def __init__(self):
        self.failure = None
        self.calls = []

    def login(self, email, password, *, request_id):
        self.calls.append((email, password, request_id))
        if self.failure:
            raise self.failure
        return CreatedSession(
            "usiar_s1.00000000-0000-4000-8000-000000000001." + "a" * 43,
            "b" * 43,
            NOW + timedelta(minutes=30),
            NOW + timedelta(hours=8),
        )


class SessionService:
    def __init__(self):
        self.failure = None
        self.calls = []

    def logout(self, token, csrf, *, request_id):
        self.calls.append((token, csrf, request_id))
        if self.failure:
            raise self.failure


def client(login=None, sessions=None):
    login = login or LoginService()
    sessions = sessions or SessionService()
    return (
        TestClient(
            create_app(
                queries=Queries(),
                settings=ApiSettings(auth_mode="internal"),
                authenticator=Authenticator(),
                internal_login_service=login,
                internal_session_service=sessions,
            ),
            raise_server_exceptions=False,
        ),
        login,
        sessions,
    )


def credentials():
    return {"email": "admin@example.com", "password": "uma senha longa e segura"}


def test_login_response_is_exact_and_never_cacheable():
    api, login, _ = client()
    response = api.post(
        "/api/v1/auth/session",
        json=credentials(),
        headers={"X-Request-ID": "safe-request"},
    )
    assert response.status_code == 201
    assert set(response.json()) == {
        "token_type",
        "session_token",
        "csrf_token",
        "idle_expires_at",
        "absolute_expires_at",
    }
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert login.calls[0][2] == "safe-request"


@pytest.mark.parametrize(
    ("failure", "status", "code"),
    [
        (InvalidCredentialsError(), 401, "INVALID_CREDENTIALS"),
        (AuthenticationRateLimitedError(17), 429, "AUTHENTICATION_RATE_LIMITED"),
        (AuthenticationCapacityError(), 503, "AUTHENTICATION_UNAVAILABLE"),
        (
            RuntimeError("postgresql://secret@host/db"),
            503,
            "AUTHENTICATION_UNAVAILABLE",
        ),
    ],
)
def test_login_errors_are_sanitized(failure, status, code, caplog):
    login = LoginService()
    login.failure = failure
    api, _, _ = client(login=login)
    response = api.post("/api/v1/auth/session", json=credentials())
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert "secret" not in response.text
    assert "secret" not in caplog.text
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "admin@example.com"},
        {**credentials(), "permission": "dashboard:read"},
        {**credentials(), "password": 123},
    ],
)
def test_login_contract_is_strict(payload):
    api, _, _ = client()
    response = api.post("/api/v1/auth/session", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_login_body_is_limited_before_authentication():
    api, login, _ = client()
    response = api.post(
        "/api/v1/auth/session",
        content=b"x" * 2049,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert login.calls == []


def test_logout_requires_bearer_and_csrf_and_is_no_store():
    api, _, sessions = client()
    missing = api.delete("/api/v1/auth/session")
    assert missing.status_code == 401
    no_csrf = api.delete(
        "/api/v1/auth/session", headers={"Authorization": "Bearer token"}
    )
    assert no_csrf.status_code == 403
    response = api.delete(
        "/api/v1/auth/session",
        headers={"Authorization": "Bearer token", "X-CSRF-Token": "c" * 43},
    )
    assert response.status_code == 204
    assert response.headers["cache-control"] == "no-store"
    assert sessions.calls


@pytest.mark.parametrize(
    ("failure", "status"),
    [
        (InvalidCsrfTokenError(), 403),
        (InvalidInternalSessionError(), 401),
        (RuntimeError("database secret"), 503),
    ],
)
def test_logout_errors_are_sanitized(failure, status):
    sessions = SessionService()
    sessions.failure = failure
    api, _, _ = client(sessions=sessions)
    response = api.delete(
        "/api/v1/auth/session",
        headers={"Authorization": "Bearer token", "X-CSRF-Token": "c" * 43},
    )
    assert response.status_code == status
    assert "secret" not in response.text


def test_internal_routes_do_not_exist_in_oidc_mode():
    api = TestClient(
        create_app(
            queries=Queries(),
            settings=ApiSettings(auth_mode="oidc"),
            authenticator=Authenticator(),
        )
    )
    assert api.post("/api/v1/auth/session", json=credentials()).status_code == 404
    assert api.delete("/api/v1/auth/session").status_code == 404


def test_missing_and_invalid_auth_mode_fail_during_initialization(monkeypatch):
    monkeypatch.delenv("AUTH_MODE", raising=False)
    with pytest.raises(ValueError, match="AUTH_MODE"):
        ApiSettings.from_environment()
    with pytest.raises(ValueError, match="AUTH_MODE"):
        ApiSettings(auth_mode="automatic")
    with pytest.raises(ValueError, match="DATABASE_URL"):
        ApiSettings(auth_mode="internal").validate_selected_authenticator()
    with pytest.raises(ValueError, match="INTERNAL_AUTH_RATE_LIMIT_KEY"):
        ApiSettings(
            auth_mode="internal", database_url="postgresql-configured-server-side"
        ).validate_selected_authenticator()
