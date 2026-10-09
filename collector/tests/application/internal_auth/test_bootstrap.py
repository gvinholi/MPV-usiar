from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from uuid import UUID

import pytest

from collector.application.internal_auth import (
    ADMIN_PERMISSIONS,
    AuditEvent,
    BootstrapAdmin,
    BootstrapAlreadyCompletedError,
    InternalPermission,
    InternalUser,
    PasswordHasher,
    normalize_email,
)
from collector.application.persistence.errors import PersistenceError
from collector.cli import auth as auth_cli
from collector.cli.auth import bootstrap_admin_interactive, parser

NOW = datetime(2026, 10, 9, 15, tzinfo=UTC)


class FakeRepository:
    def __init__(self) -> None:
        self.user: InternalUser | None = None
        self.permissions: frozenset[InternalPermission] = frozenset()
        self.events: list[AuditEvent] = []

    def bootstrap_admin(self, user, permissions, event) -> None:
        if self.user is not None:
            raise BootstrapAlreadyCompletedError("an internal user already exists")
        self.user = user
        self.permissions = permissions
        self.events.append(event)


def service(repository: FakeRepository) -> BootstrapAdmin:
    ids = iter(
        (
            UUID("00000000-0000-0000-0000-000000000001"),
            UUID("00000000-0000-0000-0000-000000000002"),
            UUID("00000000-0000-0000-0000-000000000003"),
            UUID("00000000-0000-0000-0000-000000000004"),
        )
    )
    return BootstrapAdmin(
        repository, PasswordHasher(), clock=lambda: NOW, id_factory=lambda: next(ids)
    )


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [
        ("Admin@Example.COM", "admin@example.com"),
        ("usuário@exemplo.com", "usuário@exemplo.com"),
    ],
)
def test_email_normalization(raw: str, normalized: str) -> None:
    assert normalize_email(raw) == normalized


@pytest.mark.parametrize(
    "email", [" admin@example.com", "admin@example.com ", "not-an-email"]
)
def test_rejects_ambiguous_or_invalid_email(email: str) -> None:
    with pytest.raises(ValueError, match="invalid email"):
        normalize_email(email)


def test_bootstrap_creates_active_admin_with_safe_audit() -> None:
    repository = FakeRepository()
    password = "senha de bootstrap muito forte"

    user_id = service(repository).execute("Admin@Example.COM", password)

    assert user_id == UUID("00000000-0000-0000-0000-000000000001")
    assert repository.user is not None
    assert repository.user.active
    assert repository.user.normalized_email == "admin@example.com"
    assert repository.user.email == "admin@example.com"
    assert repository.user.password_version == 1
    assert repository.user.password_hash.startswith("$argon2id$")
    assert repository.permissions == ADMIN_PERMISSIONS
    assert len(repository.events) == 1
    event = repository.events[0]
    assert event.event_type == "BOOTSTRAP_ADMIN"
    assert event.subject_user_id == user_id
    serialized = repr(asdict(event))
    assert password not in serialized
    assert repository.user.password_hash not in serialized


def test_second_bootstrap_is_refused_without_replacing_first_user() -> None:
    repository = FakeRepository()
    bootstrap = service(repository)
    first_id = bootstrap.execute("first@example.com", "primeira senha muito forte")

    with pytest.raises(BootstrapAlreadyCompletedError):
        bootstrap.execute("second@example.com", "segunda senha muito forte")

    assert repository.user is not None
    assert repository.user.id == first_id
    assert len(repository.events) == 1


def test_interactive_bootstrap_rejects_mismatched_confirmation() -> None:
    repository = FakeRepository()
    passwords = iter(("senha muito forte numero um", "senha muito forte numero dois"))

    with pytest.raises(ValueError, match="confirmation"):
        bootstrap_admin_interactive(
            service(repository),
            input_fn=lambda _prompt: "admin@example.com",
            password_fn=lambda _prompt: next(passwords),
        )

    assert repository.user is None


def test_interactive_success_prints_only_confirmation_and_uuid() -> None:
    repository = FakeRepository()
    outputs: list[str] = []

    result = bootstrap_admin_interactive(
        service(repository),
        input_fn=lambda _prompt: "admin@example.com",
        password_fn=lambda _prompt: "senha de bootstrap muito forte",
        output_fn=outputs.append,
    )

    assert result == 0
    assert outputs == ["Admin/Dev criado: 00000000-0000-0000-0000-000000000001"]
    assert "senha" not in outputs[0].casefold()
    assert "argon2" not in outputs[0].casefold()


def test_cli_has_no_password_argument() -> None:
    with pytest.raises(SystemExit):
        parser().parse_args(["bootstrap-admin", "--password", "segredo"])


def test_cli_sanitizes_persistence_failures(monkeypatch, capsys) -> None:
    def fail_safely():
        raise PersistenceError("postgresql://user:secret@example.invalid/database")

    monkeypatch.setattr(auth_cli, "create_session_factory", fail_safely)

    assert auth_cli.main(["bootstrap-admin"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "falha segura de persistencia" in captured.err
    assert "secret" not in captured.err
    assert "postgresql" not in captured.err
