"""Adaptador HTTP da API pública de consulta do PNCP."""

from collector.infra.pncp.client import DEFAULT_BASE_URL, PncpClient
from collector.infra.pncp.errors import (
    PncpError,
    PncpHttpError,
    PncpInvalidDateError,
    PncpInvalidIdentityError,
    PncpInvalidJsonError,
    PncpInvalidMoneyError,
    PncpInvalidTypeError,
    PncpMappingError,
    PncpMissingFieldError,
    PncpTimeoutError,
    PncpTransportError,
    PncpUnexpectedPayloadError,
)
from collector.infra.pncp.fetcher import PncpPublicationFetcher
from collector.infra.pncp.mapper import map_pncp_publication
from collector.infra.pncp.models import PncpPublicationPage
from collector.infra.pncp.api_resource_url import build_pncp_api_resource_url

__all__ = [
    "DEFAULT_BASE_URL",
    "PncpClient",
    "PncpError",
    "PncpHttpError",
    "PncpInvalidDateError",
    "PncpInvalidIdentityError",
    "PncpInvalidJsonError",
    "PncpInvalidMoneyError",
    "PncpInvalidTypeError",
    "PncpMappingError",
    "PncpMissingFieldError",
    "PncpPublicationFetcher",
    "PncpPublicationPage",
    "PncpTimeoutError",
    "PncpTransportError",
    "PncpUnexpectedPayloadError",
    "build_pncp_api_resource_url",
    "map_pncp_publication",
]
