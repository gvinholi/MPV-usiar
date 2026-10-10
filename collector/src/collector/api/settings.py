import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ApiSettings:
    auth_mode: str | None = None
    database_url: str | None = field(default=None, repr=False)
    internal_auth_rate_limit_key: str | None = field(default=None, repr=False)
    environment: str = "development"
    request_id_header: str = "X-Request-ID"
    cors_origins: tuple[str, ...] = ()
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    oidc_algorithms: tuple[str, ...] = ("RS256",)
    oidc_jwks_cache_seconds: int = 300
    api_docs_enabled: bool | None = None

    def __post_init__(self):
        if self.auth_mode not in {"internal", "oidc"}:
            raise ValueError("AUTH_MODE must be exactly 'internal' or 'oidc'")
        if "*" in self.cors_origins:
            raise ValueError("wildcard CORS origin is not allowed")
        if (
            type(self.oidc_jwks_cache_seconds) is not int
            or not 1 <= self.oidc_jwks_cache_seconds <= 3600
        ):
            raise ValueError(
                "OIDC JWKS cache lifetime must be between 1 and 3600 seconds"
            )

    @classmethod
    def from_environment(cls):
        raw = os.getenv("API_CORS_ORIGINS", "")
        docs_enabled = _optional_bool(os.getenv("API_DOCS_ENABLED"))
        algorithms = tuple(
            x.strip()
            for x in os.getenv("OIDC_ALGORITHMS", "RS256").split(",")
            if x.strip()
        )
        return cls(
            auth_mode=os.getenv("AUTH_MODE") or None,
            database_url=os.getenv("DATABASE_URL") or None,
            internal_auth_rate_limit_key=os.getenv("INTERNAL_AUTH_RATE_LIMIT_KEY")
            or None,
            environment=os.getenv("ENVIRONMENT", "development"),
            cors_origins=tuple(x.strip() for x in raw.split(",") if x.strip()),
            oidc_issuer=os.getenv("OIDC_ISSUER") or None,
            oidc_audience=os.getenv("OIDC_AUDIENCE") or None,
            oidc_jwks_url=os.getenv("OIDC_JWKS_URL") or None,
            oidc_algorithms=algorithms,
            oidc_jwks_cache_seconds=int(os.getenv("OIDC_JWKS_CACHE_SECONDS", "300")),
            api_docs_enabled=docs_enabled,
        )

    @property
    def oidc_configured(self) -> bool:
        return bool(self.oidc_issuer and self.oidc_audience and self.oidc_jwks_url)

    def validate_selected_authenticator(self) -> None:
        if self.auth_mode == "oidc" and not self.oidc_configured:
            raise ValueError("OIDC configuration is incomplete for AUTH_MODE=oidc")
        if self.auth_mode == "internal":
            if not self.database_url:
                raise ValueError("DATABASE_URL is required for AUTH_MODE=internal")
            if not self.internal_auth_rate_limit_key:
                raise ValueError(
                    "INTERNAL_AUTH_RATE_LIMIT_KEY is required for AUTH_MODE=internal"
                )

    @property
    def docs_enabled(self) -> bool:
        if self.api_docs_enabled is not None:
            return self.api_docs_enabled
        return self.environment.strip().lower() not in {"production", "prod"}


def _optional_bool(value: str | None) -> bool | None:
    if value is None or not value.strip():
        return None
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValueError("API_DOCS_ENABLED must be a boolean")
