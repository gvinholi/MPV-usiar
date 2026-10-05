"""Downloader HTTP em streaming — sem rede real."""

import socket

import httpx
import pytest

from collector.application import AcquisitionError, AcquisitionReason, DocumentAcquisitionPolicy
from collector.infra.acquisition import HttpxBinaryDownloader, UrlSafetyPolicy
from tests.application.acquisition.zip_fixtures import PDF_BYTES, zip_bytes


def _public_resolve(_host: str, _port: int):
    return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))]


def _client(handler, **policy) -> HttpxBinaryDownloader:
    return HttpxBinaryDownloader(
        policy=DocumentAcquisitionPolicy(max_redirects=1, **policy),
        safety=UrlSafetyPolicy(resolve=_public_resolve),
        transport=httpx.MockTransport(handler),
    )


def _read(downloader: HttpxBinaryDownloader, url: str = "https://pncp.gov.br/file") -> bytes:
    download = downloader.open(url)
    try:
        return b"".join(download.iter_chunks())
    finally:
        download.close()


def test_pdf_download() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=PDF_BYTES, headers={"content-type": "application/pdf"})

    body = _read(_client(handler))
    assert body.startswith(b"%PDF-")


def test_zip_download() -> None:
    payload = zip_bytes(("a.txt", b"ok"))

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=payload)

    assert _read(_client(handler)).startswith(b"PK")


def test_content_length_absent() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=iter([PDF_BYTES]))

    download = _client(handler).open("https://pncp.gov.br/file")
    try:
        assert download.metadata.content_length is None
        assert b"".join(download.iter_chunks()) == PDF_BYTES
    finally:
        download.close()


def test_timeout() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout")

    with pytest.raises(AcquisitionError) as exc:
        _client(handler).open("https://pncp.gov.br/file")
    assert exc.value.reason is AcquisitionReason.TIMEOUT


def test_transport() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    with pytest.raises(AcquisitionError) as exc:
        _client(handler).open("https://pncp.gov.br/file")
    assert exc.value.reason is AcquisitionReason.TRANSPORT_ERROR


def test_http_404() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="missing")

    with pytest.raises(AcquisitionError) as exc:
        _client(handler).open("https://pncp.gov.br/file")
    assert exc.value.reason is AcquisitionReason.HTTP_ERROR


def test_http_500() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="erro")

    with pytest.raises(AcquisitionError) as exc:
        _client(handler).open("https://pncp.gov.br/file")
    assert exc.value.reason is AcquisitionReason.HTTP_ERROR


def test_redirect_allowed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/old":
            return httpx.Response(302, headers={"location": "https://pncp.gov.br/new"})
        return httpx.Response(200, content=PDF_BYTES)

    download = _client(handler).open("https://pncp.gov.br/old")
    try:
        assert download.metadata.requested_url.endswith("/old")
        assert str(download.metadata.final_url).endswith("/new")
        assert b"".join(download.iter_chunks()) == PDF_BYTES
    finally:
        download.close()


def test_too_many_redirects() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://pncp.gov.br/next"})

    with pytest.raises(AcquisitionError) as exc:
        _client(handler).open("https://pncp.gov.br/old")
    assert exc.value.reason is AcquisitionReason.TOO_MANY_REDIRECTS


def test_redirect_to_private_is_blocked() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/public":
            return httpx.Response(302, headers={"location": "http://10.0.0.5/secret"})
        return httpx.Response(200, content=b"nope")

    with pytest.raises(AcquisitionError) as exc:
        _client(handler).open("https://pncp.gov.br/public")
    assert exc.value.reason is AcquisitionReason.UNSAFE_DESTINATION
