"""Compatibilidade entre uma rodada já persistida e um resultado reenviado."""

from collector.domain import CollectionRound


def rounds_compatible(stored: CollectionRound, incoming: CollectionRound) -> bool:
    return (
        stored.id == incoming.id
        and stored.source == incoming.source
        and stored.status == incoming.status
        and stored.started_at == incoming.started_at
        and stored.ended_at == incoming.ended_at
        and stored.metrics == incoming.metrics
    )
