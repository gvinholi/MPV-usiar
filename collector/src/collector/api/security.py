"""Provider-neutral OIDC Bearer authentication with asymmetric JWT/JWKS."""

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from urllib.parse import urlsplit
from uuid import UUID

import jwt
from jwt import PyJWKClient
from jwt.exceptions import (
    InvalidKeyError,
    InvalidTokenError,
    PyJWKClientConnectionError,
    PyJWKClientError,
    PyJWKSetError,
)

from collector.application.internal_auth import (
    InternalSessionService,
    InvalidInternalSessionError,
)

ASYMMETRIC_ALGORITHMS = frozenset(
    {"RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "EdDSA"}
)
MAX_BEARER_TOKEN_LENGTH = 16_384
MAX_JWKS_CACHE_SECONDS = 3_600


class AuthenticationError(Exception):
    pass


class AuthenticationUnavailableError(Exception):
    pass


class AuthenticationConfigurationError(AuthenticationUnavailableError):
    pass


class PermissionDeniedError(Exception):
    pass


class AuthenticationKind(StrEnum):
    OIDC = "oidc"
    INTERNAL = "internal"


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    issuer: str
    subject: str
    display_name: str | None
    permissions: frozenset[str]
    authentication_kind: AuthenticationKind = AuthenticationKind.OIDC

    def __post_init__(self):
        if not self.issuer or not self.subject:
            raise AuthenticationError("invalid identity")
        if self.display_name is not None and (
            not self.display_name.strip() or len(self.display_name) > 200
        ):
            raise AuthenticationError("invalid display name")

    @property
    def reviewer_id(self) -> str:
        if self.authentication_kind is AuthenticationKind.INTERNAL:
            try:
                value = f"internal:{UUID(self.subject)}"
            except (ValueError, TypeError) as exc:
                raise AuthenticationError("invalid internal identity") from exc
            if value != f"internal:{self.subject}":
                raise AuthenticationError("invalid internal identity")
            return value
        # Length-prefixing makes the issuer/subject boundary reversible and unambiguous.
        value = f"oidc:{len(self.issuer)}:{self.issuer}{self.subject}"
        if len(value) > 200:
            raise AuthenticationError("authenticated identity exceeds reviewer limit")
        return value


class TokenAuthenticator(Protocol):
    def authenticate(self, token: str) -> AuthenticatedPrincipal: ...


def require_permission(
    principal: AuthenticatedPrincipal, permission: str
) -> AuthenticatedPrincipal:
    if permission not in principal.permissions:
        raise PermissionDeniedError(f"{permission} required")
    return principal


class OidcJwtAuthenticator:
    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        jwks_url: str,
        algorithms: tuple[str, ...] = ("RS256",),
        cache_seconds: int = 300,
    ):
        if not issuer or not audience or not jwks_url:
            raise AuthenticationConfigurationError("OIDC configuration incomplete")
        if not algorithms or any(
            value not in ASYMMETRIC_ALGORITHMS for value in algorithms
        ):
            raise AuthenticationConfigurationError(
                "OIDC algorithms must be asymmetric and explicitly allowed"
            )
        if (
            type(cache_seconds) is not int
            or not 1 <= cache_seconds <= MAX_JWKS_CACHE_SECONDS
        ):
            raise AuthenticationConfigurationError(
                "OIDC JWKS cache lifetime must be between 1 and 3600 seconds"
            )
        jwks_url = _validated_jwks_url(jwks_url)
        self._issuer = issuer
        self._audience = audience
        self._algorithms = algorithms
        self._jwks = PyJWKClient(
            jwks_url,
            cache_jwk_set=True,
            lifespan=cache_seconds,
            cache_keys=False,
            timeout=5,
        )

    def authenticate(self, token: str) -> AuthenticatedPrincipal:
        if not token or len(token) > MAX_BEARER_TOKEN_LENGTH:
            raise AuthenticationError("invalid bearer token")
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") not in self._algorithms:
                raise AuthenticationError("token algorithm is not allowed")
            signing_key = self._jwks.get_signing_key_from_jwt(token)
            if signing_key.algorithm_name != header["alg"]:
                raise AuthenticationError("token and signing key algorithms differ")
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=list(self._algorithms),
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["iss", "aud", "exp", "sub"]},
            )
        except AuthenticationError:
            raise
        except (
            PyJWKClientConnectionError,
            PyJWKSetError,
            InvalidKeyError,
            json.JSONDecodeError,
        ) as exc:
            raise AuthenticationUnavailableError(
                "OIDC key service unavailable"
            ) from exc
        except InvalidTokenError as exc:
            raise AuthenticationError("invalid bearer token") from exc
        except PyJWKClientError as exc:
            if str(exc).startswith("Unable to find a signing key that matches:"):
                raise AuthenticationError("invalid bearer token") from exc
            raise AuthenticationUnavailableError(
                "OIDC key service unavailable"
            ) from exc
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject.strip():
            raise AuthenticationError("invalid subject")
        scope = claims.get("scope", "")
        if not isinstance(scope, str):
            raise AuthenticationError("invalid scope")
        name = claims.get("name")
        display_name = (
            name.strip()
            if isinstance(name, str) and name.strip() and len(name.strip()) <= 200
            else None
        )
        principal = AuthenticatedPrincipal(
            self._issuer, subject, display_name, frozenset(scope.split())
        )
        _ = principal.reviewer_id  # validate before authorization succeeds
        return principal


class InternalSessionAuthenticator:
    def __init__(self, session_service: InternalSessionService) -> None:
        self._session_service = session_service

    def authenticate(self, token: str) -> AuthenticatedPrincipal:
        if not token or len(token) > MAX_BEARER_TOKEN_LENGTH:
            raise AuthenticationError("invalid bearer token")
        try:
            identity = self._session_service.authenticate(token)
        except InvalidInternalSessionError as exc:
            raise AuthenticationError("invalid bearer token") from exc
        except Exception as exc:
            raise AuthenticationUnavailableError(
                "internal session store unavailable"
            ) from exc
        principal = AuthenticatedPrincipal(
            issuer="urn:mpv-usiar:internal",
            subject=str(identity.user_id),
            display_name=identity.display_name,
            permissions=identity.permissions,
            authentication_kind=AuthenticationKind.INTERNAL,
        )
        _ = principal.reviewer_id
        return principal


def _validated_jwks_url(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(char.isspace() for char in value)
    ):
        raise AuthenticationConfigurationError("OIDC JWKS URL is invalid")
    try:
        parsed = urlsplit(value)
        _ = parsed.port  # force validation of malformed ports
    except ValueError as exc:
        raise AuthenticationConfigurationError("OIDC JWKS URL is invalid") from exc
    if (
        parsed.scheme.lower() != "https"
        or not parsed.netloc
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise AuthenticationConfigurationError(
            "OIDC JWKS URL must be a credential-free HTTPS URL"
        )
    return value
