"""Consolida observações por identidade externa exata.

Agrupa componentes conectados: se A compartilha identidade com B e B
compartilha outra com C, A, B e C formam um único grupo. Sem
similaridade aproximada e sem equivalência entre fontes sem identidade
compartilhada.
"""

from __future__ import annotations

from collector.application.consolidation.errors import ConsolidationError
from collector.application.consolidation.results import (
    ConsolidatedProcess,
    ConsolidationResult,
)
from collector.domain import Process, SourceIdentity


class ProcessConsolidator:
    def consolidate(self, processes: tuple[Process, ...] | list[Process]) -> ConsolidationResult:
        observations = tuple(processes)
        try:
            groups = _group(observations)
        except ConsolidationError:
            raise
        except Exception as exc:
            raise ConsolidationError("falha estrutural na consolidação") from exc
        return ConsolidationResult(
            observations_received=len(observations),
            unique_processes=len(groups),
            duplicates=len(observations) - len(groups),
            groups=groups,
        )


def _group(observations: tuple[Process, ...]) -> tuple[ConsolidatedProcess, ...]:
    if not observations:
        return ()
    parent = list(range(len(observations)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        root_left, root_right = find(left), find(right)
        if root_left == root_right:
            return
        if root_left < root_right:
            parent[root_right] = root_left
        else:
            parent[root_left] = root_right

    first_seen: dict[SourceIdentity, int] = {}
    for index, observation in enumerate(observations):
        if not observation.source_identities:
            raise ConsolidationError("observação sem identidade externa")
        for identity in observation.source_identities:
            owner = first_seen.get(identity)
            if owner is None:
                first_seen[identity] = index
            else:
                union(index, owner)

    members: dict[int, list[int]] = {}
    for index in range(len(observations)):
        members.setdefault(find(index), []).append(index)

    groups: list[ConsolidatedProcess] = []
    for root in sorted(members):
        indexes = members[root]
        representative = observations[_representative_index(indexes, observations)]
        identities = _first_seen_identities(indexes, observations)
        observed = tuple(observations[index] for index in indexes)
        groups.append(
            ConsolidatedProcess(
                process=representative,
                identities=identities,
                observations=observed,
                observation_count=len(observed),
            )
        )
    return tuple(groups)


def _representative_index(indexes: list[int], observations: tuple[Process, ...]) -> int:
    chosen = indexes[0]
    for index in indexes[1:]:
        if _is_more_recent(observations[index], observations[chosen]):
            chosen = index
    return chosen


def _is_more_recent(candidate: Process, current: Process) -> bool:
    candidate_at = candidate.last_captured_at
    current_at = current.last_captured_at
    if candidate_at is None:
        return False
    if current_at is None:
        return True
    return candidate_at > current_at


def _first_seen_identities(
    indexes: list[int],
    observations: tuple[Process, ...],
) -> tuple[SourceIdentity, ...]:
    seen: list[SourceIdentity] = []
    known: set[SourceIdentity] = set()
    for index in indexes:
        for identity in observations[index].source_identities:
            if identity not in known:
                known.add(identity)
                seen.append(identity)
    return tuple(seen)
