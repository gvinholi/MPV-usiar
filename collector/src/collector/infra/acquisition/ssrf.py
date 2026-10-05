"""Política de destino HTTP. URL é entrada externa, mesmo vinda do PNCP.

A resolução DNS ocorre no momento da verificação. Existe janela TOCTOU
(DNS rebinding) entre o check e o connect; isto não é um firewall.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable, Sequence
from urllib.parse import urlparse

from collector.application.acquisition.errors import AcquisitionError
from collector.application.acquisition.reasons import AcquisitionReason

Resolver = Callable[[str, int], Sequence[tuple[int, int, int, str, tuple]]]

_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "ip6-localhost",
        "ip6-loopback",
    }
)


class UrlSafetyPolicy:
    def __init__(self, *, resolve: Resolver | None = None) -> None:
        self._resolve = resolve or _default_resolve

    def assert_safe(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise AcquisitionError(
                "apenas http e https são permitidos",
                reason=AcquisitionReason.INVALID_URL,
            )
        host = parsed.hostname
        if not host:
            raise AcquisitionError(
                "URL sem hostname",
                reason=AcquisitionReason.INVALID_URL,
            )
        if host.strip("[]").lower() in _BLOCKED_HOSTNAMES:
            raise AcquisitionError(
                "destino local bloqueado",
                reason=AcquisitionReason.UNSAFE_DESTINATION,
            )
        port = parsed.port if parsed.port is not None else 0
        try:
            literal = ipaddress.ip_address(host.strip("[]"))
        except ValueError:
            literal = None
        if literal is not None:
            _assert_public_ip(literal)
            return
        try:
            answers = self._resolve(host, port)
        except OSError as exc:
            raise AcquisitionError(
                "falha ao resolver destino",
                reason=AcquisitionReason.UNSAFE_DESTINATION,
            ) from exc
        if not answers:
            raise AcquisitionError(
                "destino sem endereço resolvido",
                reason=AcquisitionReason.UNSAFE_DESTINATION,
            )
        for answer in answers:
            address = answer[4][0]
            _assert_public_ip(ipaddress.ip_address(address))


def _assert_public_ip(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    if address.version == 6 and address.ipv4_mapped is not None:
        _assert_public_ip(address.ipv4_mapped)
        return
    if (
        address.is_loopback
        or address.is_private
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
        or not address.is_global
    ):
        raise AcquisitionError(
            "destino privado ou não roteável bloqueado",
            reason=AcquisitionReason.UNSAFE_DESTINATION,
        )


def _default_resolve(host: str, port: int) -> Sequence[tuple[int, int, int, str, tuple]]:
    return socket.getaddrinfo(host, port or None, type=socket.SOCK_STREAM)
