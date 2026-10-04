"""Resolução de identidade persistente entre rodadas.

Agrupa somente por interseção exata de SourceIdentity. Sem fuzzy e sem
escolha silenciosa quando identidades já pertencem a processos distintos.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from collector.domain import SourceIdentity


@dataclass(frozen=True)
class CreateProcess:
    identities: tuple[SourceIdentity, ...]


@dataclass(frozen=True)
class ReuseProcess:
    process_id: UUID
    new_identities: tuple[SourceIdentity, ...]


@dataclass(frozen=True)
class IdentityConflict:
    process_ids: tuple[UUID, ...]
    identities: tuple[SourceIdentity, ...]


IdentityDecision = CreateProcess | ReuseProcess | IdentityConflict


def resolve_identities(
    identities: tuple[SourceIdentity, ...],
    existing: Mapping[SourceIdentity, UUID],
) -> IdentityDecision:
    if not identities:
        raise ValueError("grupo sem identidade externa")
    found = {existing[identity] for identity in identities if identity in existing}
    if not found:
        return CreateProcess(identities)
    if len(found) == 1:
        process_id = next(iter(found))
        new_identities = tuple(
            identity for identity in identities if identity not in existing
        )
        return ReuseProcess(process_id, new_identities)
    return IdentityConflict(
        process_ids=tuple(sorted(found, key=str)),
        identities=identities,
    )
