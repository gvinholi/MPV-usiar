"""Identidade determinística do conjunto documental analisado."""

from __future__ import annotations

import hashlib

from collector.application.screening.profile import ScreeningProfile

FINGERPRINT_ALGORITHM = "sha256"


def document_set_fingerprint(
    profile: ScreeningProfile,
    engine_version: str,
    member_sha256s: tuple[str, ...] | list[str],
) -> str:
    """SHA-256 de profile code/version + engine + members ordenados.

    Não usa UUID de row, timestamp, acquisition_id nem path. Ordem de
    entrada dos members é irrelevante: a lista é ordenada.
    """

    lines = [
        f"{profile.code}/{profile.version}",
        engine_version,
        *sorted(digest.strip().lower() for digest in member_sha256s),
    ]
    payload = "\n".join(lines).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
