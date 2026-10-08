from dataclasses import dataclass, field
import os

@dataclass(frozen=True)
class ApiSettings:
    database_url: str | None = field(default=None, repr=False)
    environment: str = "development"
    request_id_header: str = "X-Request-ID"
    cors_origins: tuple[str, ...] = ()
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    oidc_algorithms: tuple[str, ...] = ("RS256",)
    oidc_jwks_cache_seconds: int = 300

    def __post_init__(self):
        if "*" in self.cors_origins:
            raise ValueError("wildcard CORS origin is not allowed")
        if type(self.oidc_jwks_cache_seconds) is not int or not 1 <= self.oidc_jwks_cache_seconds <= 3600:
            raise ValueError("OIDC JWKS cache lifetime must be between 1 and 3600 seconds")

    @classmethod
    def from_environment(cls):
        raw = os.getenv("API_CORS_ORIGINS", "")
        algorithms = tuple(x.strip() for x in os.getenv("OIDC_ALGORITHMS", "RS256").split(",") if x.strip())
        return cls(database_url=os.getenv("DATABASE_URL") or None,
                   environment=os.getenv("ENVIRONMENT", "development"),
                   cors_origins=tuple(x.strip() for x in raw.split(",") if x.strip()),
                   oidc_issuer=os.getenv("OIDC_ISSUER") or None,
                   oidc_audience=os.getenv("OIDC_AUDIENCE") or None,
                   oidc_jwks_url=os.getenv("OIDC_JWKS_URL") or None,
                   oidc_algorithms=algorithms,
                   oidc_jwks_cache_seconds=int(os.getenv("OIDC_JWKS_CACHE_SECONDS", "300")))

    @property
    def oidc_configured(self) -> bool:
        return bool(self.oidc_issuer and self.oidc_audience and self.oidc_jwks_url)
