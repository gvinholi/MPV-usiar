"""Cliente HTTP de binários. Streaming, sem JSON e sem persistência."""

from __future__ import annotations

import re
from collections.abc import Iterator
from urllib.parse import urljoin

import httpx

from collector.application.acquisition.errors import AcquisitionError
from collector.application.acquisition.policy import DocumentAcquisitionPolicy
from collector.application.acquisition.ports import BinaryDownload, DownloadMetadata
from collector.application.acquisition.reasons import AcquisitionReason
from collector.infra.acquisition.ssrf import UrlSafetyPolicy

_REDIRECTS = {301, 302, 303, 307, 308}
_CONTENT_DISPOSITION_NAME = re.compile(
    r"filename\*?=(?:UTF-8''|\"?)([^\";]+)",
    re.IGNORECASE,
)


class StreamingBinaryDownload:
    def __init__(
        self,
        *,
        metadata: DownloadMetadata,
        response: httpx.Response,
        client: httpx.Client,
    ) -> None:
        self.metadata = metadata
        self._response = response
        self._client = client

    def iter_chunks(self) -> Iterator[bytes]:
        yield from self._response.iter_bytes()

    def close(self) -> None:
        self._response.close()
        self._client.close()


class HttpxBinaryDownloader:
    def __init__(
        self,
        *,
        policy: DocumentAcquisitionPolicy | None = None,
        safety: UrlSafetyPolicy | None = None,
        transport: httpx.BaseTransport | None = None,
        user_agent: str = "usiar-collector/0.1",
    ) -> None:
        self._policy = policy or DocumentAcquisitionPolicy()
        self._safety = safety or UrlSafetyPolicy()
        self._transport = transport
        self._user_agent = user_agent

    def open(self, url: str) -> BinaryDownload:
        requested = url
        current = url
        client = httpx.Client(
            timeout=self._policy.timeout_seconds,
            follow_redirects=False,
            headers={"User-Agent": self._user_agent},
            transport=self._transport,
        )
        try:
            for hop in range(self._policy.max_redirects + 1):
                self._safety.assert_safe(current)
                try:
                    response = client.send(
                        client.build_request("GET", current),
                        stream=True,
                    )
                except httpx.TimeoutException as exc:
                    raise AcquisitionError(
                        "timeout ao baixar artefato",
                        reason=AcquisitionReason.TIMEOUT,
                    ) from exc
                except httpx.TransportError as exc:
                    raise AcquisitionError(
                        "falha de transporte ao baixar artefato",
                        reason=AcquisitionReason.TRANSPORT_ERROR,
                    ) from exc
                if response.status_code in _REDIRECTS:
                    location = response.headers.get("location")
                    response.close()
                    if not location:
                        raise AcquisitionError(
                            "redirect sem Location",
                            reason=AcquisitionReason.HTTP_ERROR,
                        )
                    current = urljoin(current, location)
                    if hop >= self._policy.max_redirects:
                        raise AcquisitionError(
                            "excesso de redirects",
                            reason=AcquisitionReason.TOO_MANY_REDIRECTS,
                        )
                    continue
                if response.status_code != 200:
                    status = response.status_code
                    response.close()
                    raise AcquisitionError(
                        f"HTTP {status} ao baixar artefato",
                        reason=AcquisitionReason.HTTP_ERROR,
                    )
                metadata = DownloadMetadata(
                    requested_url=requested,
                    final_url=str(response.url),
                    status_code=response.status_code,
                    content_type=response.headers.get("content-type"),
                    content_length=_content_length(response),
                    original_filename=_filename(response),
                )
                return StreamingBinaryDownload(
                    metadata=metadata,
                    response=response,
                    client=client,
                )
            raise AcquisitionError(
                "excesso de redirects",
                reason=AcquisitionReason.TOO_MANY_REDIRECTS,
            )
        except Exception:
            client.close()
            raise


def _content_length(response: httpx.Response) -> int | None:
    raw = response.headers.get("content-length")
    if raw is None:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value >= 0 else None


def _filename(response: httpx.Response) -> str | None:
    header = response.headers.get("content-disposition")
    if not header:
        return None
    match = _CONTENT_DISPOSITION_NAME.search(header)
    if match is None:
        return None
    name = match.group(1).strip().strip('"')
    return name or None
