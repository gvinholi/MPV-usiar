from __future__ import annotations

import pytest
from argon2 import PasswordHasher as Argon2PasswordHasher
from argon2 import Type

from collector.application.internal_auth.passwords import (
    ARGON2_MEMORY_KIB,
    ARGON2_PARALLELISM,
    ARGON2_TIME_COST,
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    PasswordHasher,
    PasswordPolicyError,
)


def test_argon2id_parameters_random_salt_and_verification() -> None:
    hasher = PasswordHasher()
    password = "  Senha Unicode segura ☃  "

    first = hasher.hash(password)
    second = hasher.hash(password)

    assert first != second
    assert first.startswith("$argon2id$v=19$m=19456,t=2,p=1$")
    assert hasher.verify(first, password)
    assert not hasher.verify(first, password.strip())
    assert not hasher.verify(first, "senha incorreta")
    assert not hasher.verify("hash-invalido", password)
    assert not hasher.needs_rehash("hash-invalido")


@pytest.mark.parametrize(
    "password",
    ["x" * (MIN_PASSWORD_LENGTH - 1), "x" * (MAX_PASSWORD_LENGTH + 1), " " * 15],
)
def test_password_length_and_content_limits(password: str) -> None:
    with pytest.raises(PasswordPolicyError):
        PasswordHasher().hash(password)


def test_valid_boundary_lengths() -> None:
    hasher = PasswordHasher()

    assert hasher.verify(
        hasher.hash("x" * MIN_PASSWORD_LENGTH), "x" * MIN_PASSWORD_LENGTH
    )
    assert hasher.verify(
        hasher.hash("x" * MAX_PASSWORD_LENGTH), "x" * MAX_PASSWORD_LENGTH
    )


def test_detects_hash_requiring_rehash() -> None:
    legacy = Argon2PasswordHasher(
        time_cost=1,
        memory_cost=8 * 1024,
        parallelism=1,
        hash_len=32,
        salt_len=16,
        type=Type.ID,
    ).hash("senha suficientemente longa")
    hasher = PasswordHasher()

    assert hasher.verify(legacy, "senha suficientemente longa")
    assert hasher.needs_rehash(legacy)
    current = hasher.hash("senha suficientemente longa")
    assert not hasher.needs_rehash(current)
    assert (
        f"m={ARGON2_MEMORY_KIB},t={ARGON2_TIME_COST},p={ARGON2_PARALLELISM}" in current
    )
