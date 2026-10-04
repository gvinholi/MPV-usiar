"""Adaptador: PncpClient (uma página) → porta de aplicação."""

from __future__ import annotations

from collector.application.publications.errors import PermanentFetchError, TransientFetchError
from collector.application.publications.query import PublicationQuery
from collector.application.publications.results import PublicationPage
from collector.infra.pncp.client import PncpClient
from collector.infra.pncp.errors import (
    PncpHttpError,
    PncpInvalidJsonError,
    PncpTimeoutError,
    PncpTransportError,
    PncpUnexpectedPayloadError,
)


class PncpPublicationFetcher:
    def __init__(self, client: PncpClient) -> None:
        self._client = client

    def fetch_page(self, query: PublicationQuery, page: int) -> PublicationPage:
        try:
            raw = self._client.get_publications(
                start_date=query.start_date,
                end_date=query.end_date,
                modality_code=query.modality_code,
                page=page,
                uf=query.uf,
                dispute_mode_code=query.dispute_mode_code,
                ibge_municipality_code=query.ibge_municipality_code,
                cnpj=query.cnpj,
                administrative_unit_code=query.administrative_unit_code,
                user_id=query.user_id,
                page_size=query.page_size,
            )
        except (PncpTimeoutError, PncpTransportError) as exc:
            raise TransientFetchError(str(exc)) from exc
        except PncpHttpError as exc:
            if exc.status_code == 429 or exc.status_code >= 500:
                raise TransientFetchError(str(exc), status_code=exc.status_code) from exc
            raise PermanentFetchError(str(exc), status_code=exc.status_code) from exc
        except (PncpInvalidJsonError, PncpUnexpectedPayloadError) as exc:
            raise PermanentFetchError(str(exc)) from exc

        return PublicationPage(
            data=raw.data,
            total_registros=raw.total_registros,
            total_paginas=raw.total_paginas,
            numero_pagina=raw.numero_pagina,
            paginas_restantes=raw.paginas_restantes,
            empty=raw.empty,
        )
