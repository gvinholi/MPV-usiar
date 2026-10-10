"""Versioned opaque session and CSRF token primitives."""

from __future__ import annotations

import base64
import hashlib
import re
import secrets
from dataclasses import dataclass
from uuid import UUID, uuid4

_SECRET_RE = re.compile(r"[A-Za-z0-9_-]{43}")
_SESSION_RE = re.compile(
    r"usiar_s1\.([0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})\.([A-Za-z0-9_-]{43})"
)


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    if _SECRET_RE.fullmatch(value) is None:
        raise ValueError("invalid secret")
    decoded = base64.urlsafe_b64decode(value + "=")
    if len(decoded) != 32 or _encode(decoded) != value:
        raise ValueError("invalid secret")
    return decoded


def digest_secret(value: bytes) -> bytes:
    return hashlib.sha256(value).digest()


@dataclass(frozen=True)
class GeneratedSessionSecrets:
    session_id: UUID
    session_token: str
    verifier_digest: bytes
    csrf_token: str
    csrf_digest: bytes


def generate_session_secrets() -> GeneratedSessionSecrets:
    session_id = uuid4()
    verifier = secrets.token_bytes(32)
    csrf = secrets.token_bytes(32)
    encoded_verifier = _encode(verifier)
    return GeneratedSessionSecrets(
        session_id=session_id,
        session_token=f"usiar_s1.{session_id}.{encoded_verifier}",
        verifier_digest=digest_secret(verifier),
        csrf_token=_encode(csrf),
        csrf_digest=digest_secret(csrf),
    )


def parse_session_token(value: str) -> tuple[UUID, bytes]:
    match = _SESSION_RE.fullmatch(value) if isinstance(value, str) else None
    if match is None:
        raise ValueError("invalid session token")
    session_id = UUID(match.group(1))
    if str(session_id) != match.group(1):
        raise ValueError("non-canonical session id")
    return session_id, digest_secret(_decode(match.group(2)))


def parse_csrf_token(value: str) -> bytes:
    return digest_secret(_decode(value))
