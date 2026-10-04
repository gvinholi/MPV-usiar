"""Adaptador HTTP da API pública de consulta do PNCP."""

from collector.infra.pncp.client import DEFAULT_BASE_URL, PncpClient
from collector.infra.pncp.errors import (
    PncpError,
    PncpHttpError,
    PncpInvalidJsonError,
    PncpTimeoutError,
    PncpTransportError,
    PncpUnexpectedPayloadError,
)
from collector.infra.pncp.models import PncpPublicationPage

__all__ = [
    "DEFAULT_BASE_URL",
    "PncpClient",
    "PncpError",
    "PncpHttpError",
    "PncpInvalidJsonError",
    "PncpPublicationPage",
    "PncpTimeoutError",
    "PncpTransportError",
    "PncpUnexpectedPayloadError",
]
