"""Destinos privados são bloqueados por IP, não por substring."""

import socket

import pytest

from collector.application import AcquisitionError, AcquisitionReason
from collector.infra.acquisition import UrlSafetyPolicy


def _public_resolve(_host: str, _port: int):
    return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))]


def _private_resolve(_host: str, _port: int):
    return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.0.0.8", 0))]


def test_localhost_hostname() -> None:
    with pytest.raises(AcquisitionError) as exc:
        UrlSafetyPolicy(resolve=_public_resolve).assert_safe("http://localhost/file")
    assert exc.value.reason is AcquisitionReason.UNSAFE_DESTINATION


def test_loopback_ipv4() -> None:
    with pytest.raises(AcquisitionError) as exc:
        UrlSafetyPolicy().assert_safe("http://127.0.0.1/file")
    assert exc.value.reason is AcquisitionReason.UNSAFE_DESTINATION


def test_loopback_ipv6() -> None:
    with pytest.raises(AcquisitionError) as exc:
        UrlSafetyPolicy().assert_safe("http://[::1]/file")
    assert exc.value.reason is AcquisitionReason.UNSAFE_DESTINATION


def test_rfc1918() -> None:
    with pytest.raises(AcquisitionError):
        UrlSafetyPolicy().assert_safe("http://192.168.10.4/a")
    with pytest.raises(AcquisitionError):
        UrlSafetyPolicy().assert_safe("http://10.1.2.3/a")
    with pytest.raises(AcquisitionError):
        UrlSafetyPolicy().assert_safe("http://172.16.0.9/a")


def test_link_local() -> None:
    with pytest.raises(AcquisitionError):
        UrlSafetyPolicy().assert_safe("http://169.254.169.254/latest")


def test_file_scheme() -> None:
    with pytest.raises(AcquisitionError) as exc:
        UrlSafetyPolicy().assert_safe("file:///etc/passwd")
    assert exc.value.reason is AcquisitionReason.INVALID_URL


def test_public_hostname_with_public_resolution() -> None:
    UrlSafetyPolicy(resolve=_public_resolve).assert_safe("https://pncp.gov.br/arquivo")


def test_public_hostname_resolving_private_is_blocked() -> None:
    with pytest.raises(AcquisitionError) as exc:
        UrlSafetyPolicy(resolve=_private_resolve).assert_safe("https://evil.example/x")
    assert exc.value.reason is AcquisitionReason.UNSAFE_DESTINATION
