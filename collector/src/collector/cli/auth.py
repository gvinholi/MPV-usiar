"""Interactive administration for internal authentication."""

from __future__ import annotations

import argparse
import getpass
import sys
from collections.abc import Callable, Sequence

from sqlalchemy.exc import SQLAlchemyError

from collector.application.internal_auth import (
    BootstrapAdmin,
    BootstrapAlreadyCompletedError,
    PasswordPolicyError,
)
from collector.application.persistence.errors import PersistenceError
from collector.infra.database import (
    SqlAlchemyInternalAuthRepository,
    create_session_factory,
)


def bootstrap_admin_interactive(
    service: BootstrapAdmin,
    *,
    input_fn: Callable[[str], str] = input,
    password_fn: Callable[[str], str] = getpass.getpass,
    output_fn: Callable[[str], None] = print,
) -> int:
    email = input_fn("E-mail: ")
    password = password_fn("Senha: ")
    confirmation = password_fn("Confirme a senha: ")
    if password != confirmation:
        raise PasswordPolicyError("password confirmation does not match")
    user_id = service.execute(email, password)
    output_fn(f"Admin/Dev criado: {user_id}")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Administracao da autenticacao interna USIAR."
    )
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "bootstrap-admin", help="Cria interativamente o primeiro Admin/Dev."
    )
    return result


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    if arguments.command != "bootstrap-admin":
        return 2
    try:
        repository = SqlAlchemyInternalAuthRepository(create_session_factory())
        return bootstrap_admin_interactive(BootstrapAdmin(repository))
    except (
        BootstrapAlreadyCompletedError,
        PasswordPolicyError,
        ValueError,
        RuntimeError,
    ) as exc:
        print(f"Bootstrap recusado: {exc}", file=sys.stderr)
        return 1
    except (PersistenceError, SQLAlchemyError):
        print("Bootstrap recusado: falha segura de persistencia.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
