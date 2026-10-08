from dataclasses import dataclass, field
import os

@dataclass(frozen=True)
class ApiSettings:
    database_url: str | None = field(default=None, repr=False)
    environment: str = "development"
    request_id_header: str = "X-Request-ID"
    cors_origins: tuple[str, ...] = ()

    def __post_init__(self):
        if "*" in self.cors_origins:
            raise ValueError("wildcard CORS origin is not allowed")

    @classmethod
    def from_environment(cls):
        raw = os.getenv("API_CORS_ORIGINS", "")
        return cls(database_url=os.getenv("DATABASE_URL") or None,
                   environment=os.getenv("ENVIRONMENT", "development"),
                   cors_origins=tuple(x.strip() for x in raw.split(",") if x.strip()))
