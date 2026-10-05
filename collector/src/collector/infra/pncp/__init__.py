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
from collector.infra.pncp.publication_mapper import PncpPublicationMapper
from collector.infra.pncp.api_resource_url import build_pncp_api_resource_url
from collector.infra.pncp.document_client import (
    DEFAULT_DOCUMENTS_BASE_URL,
    PncpDocumentClient,
)
from collector.infra.pncp.document_fetcher import PncpDocumentFetcher
from collector.infra.pncp.document_identity import build_pncp_document_official_id
from collector.infra.pncp.document_mapper import PncpDocumentMapper

__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_DOCUMENTS_BASE_URL",
    "PncpClient",
    "PncpDocumentClient",
    "PncpDocumentFetcher",
    "PncpDocumentMapper",
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
    "PncpPublicationMapper",
    "PncpPublicationPage",
    "PncpTimeoutError",
    "PncpTransportError",
    "PncpUnexpectedPayloadError",
    "build_pncp_api_resource_url",
    "build_pncp_document_official_id",
    "map_pncp_publication",
]
