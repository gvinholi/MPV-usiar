"""Adaptador: PncpDocumentClient → porta de aplicação."""

from __future__ import annotations

from collections.abc import Mapping

from collector.application.documents.query import DocumentQuery
from collector.application.publications.errors import PermanentFetchError, TransientFetchError
from collector.infra.pncp.document_client import PncpDocumentClient
from collector.infra.pncp.errors import (
    PncpHttpError,
    PncpInvalidJsonError,
    PncpTimeoutError,
    PncpTransportError,
    PncpUnexpectedPayloadError,
)


class PncpDocumentFetcher:
    def __init__(self, client: PncpDocumentClient) -> None:
        self._client = client

    def fetch_documents(self, query: DocumentQuery) -> tuple[Mapping[str, object], ...]:
        try:
            return self._client.get_documents(
                cnpj=query.cnpj,
                year=query.year,
                sequential=query.sequential,
            )
        except (PncpTimeoutError, PncpTransportError) as exc:
            raise TransientFetchError(str(exc)) from exc
        except PncpHttpError as exc:
            if exc.status_code == 429 or exc.status_code >= 500:
                raise TransientFetchError(str(exc), status_code=exc.status_code) from exc
            raise PermanentFetchError(str(exc), status_code=exc.status_code) from exc
        except (PncpInvalidJsonError, PncpUnexpectedPayloadError) as exc:
            raise PermanentFetchError(str(exc)) from exc
