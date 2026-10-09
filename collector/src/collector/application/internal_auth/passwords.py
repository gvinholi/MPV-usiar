"""Argon2id password hashing with explicit resource bounds."""

from argon2 import PasswordHasher as Argon2PasswordHasher
from argon2 import Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

MIN_PASSWORD_LENGTH = 15
MAX_PASSWORD_LENGTH = 128
ARGON2_MEMORY_KIB = 19 * 1024
ARGON2_TIME_COST = 2
ARGON2_PARALLELISM = 1


class PasswordPolicyError(ValueError):
    pass


def validate_password(password: str) -> None:
    if (
        not isinstance(password, str)
        or not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH
    ):
        raise PasswordPolicyError(
            f"password must contain {MIN_PASSWORD_LENGTH}..{MAX_PASSWORD_LENGTH} characters"
        )
    if not password.strip():
        raise PasswordPolicyError("password cannot contain only whitespace")


class PasswordHasher:
    def __init__(self) -> None:
        self._hasher = Argon2PasswordHasher(
            time_cost=ARGON2_TIME_COST,
            memory_cost=ARGON2_MEMORY_KIB,
            parallelism=ARGON2_PARALLELISM,
            hash_len=32,
            salt_len=16,
            type=Type.ID,
        )

    def hash(self, password: str) -> str:
        validate_password(password)
        return self._hasher.hash(password)

    def verify(self, encoded_hash: str, password: str) -> bool:
        if not isinstance(password, str) or len(password) > MAX_PASSWORD_LENGTH:
            return False
        try:
            return self._hasher.verify(encoded_hash, password)
        except (InvalidHashError, VerificationError, VerifyMismatchError, TypeError):
            return False

    def needs_rehash(self, encoded_hash: str) -> bool:
        try:
            return self._hasher.check_needs_rehash(encoded_hash)
        except (InvalidHashError, TypeError):
            return False
