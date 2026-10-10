"""Privacy-preserving keys and fixed policy for login throttling."""

from __future__ import annotations

import base64
import hashlib
import hmac
from dataclasses import dataclass


@dataclass(frozen=True)
class LoginRatePolicy:
    identifier_limit: int = 5
    identifier_window_seconds: int = 15 * 60
    identifier_block_seconds: int = 15 * 60
    global_limit: int = 60
    global_window_seconds: int = 60
    global_block_seconds: int = 60


class RateLimitKeyDeriver:
    def __init__(self, encoded_secret: str) -> None:
        if not isinstance(encoded_secret, str) or not encoded_secret:
            raise ValueError("INTERNAL_AUTH_RATE_LIMIT_KEY is required")
        try:
            padded = encoded_secret + "=" * (-len(encoded_secret) % 4)
            secret = base64.b64decode(padded, altchars=b"-_", validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError("INTERNAL_AUTH_RATE_LIMIT_KEY must be base64url") from exc
        canonical = base64.urlsafe_b64encode(secret).rstrip(b"=").decode("ascii")
        if canonical != encoded_secret or len(secret) < 32:
            raise ValueError(
                "INTERNAL_AUTH_RATE_LIMIT_KEY must contain at least 32 random bytes"
            )
        self._secret = secret

    def identifier(self, normalized_email: str) -> bytes:
        return self._derive(b"identifier\x00" + normalized_email.encode("utf-8"))

    def global_key(self) -> bytes:
        return self._derive(b"global\x00login")

    def _derive(self, message: bytes) -> bytes:
        return hmac.new(self._secret, message, hashlib.sha256).digest()
