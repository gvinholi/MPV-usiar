"""Compatibilidade entre uma rodada já persistida e um resultado reenviado."""

from collector.domain import CollectionRound


def rounds_compatible(stored: CollectionRound, incoming: CollectionRound) -> bool:
    # Métricas de triagem/documentos são enriquecidas por etapas posteriores.
    # A idempotência da coleta compara somente os campos que ela própria produz.
    collection_metric_names = (
        "pages_expected",
        "pages_processed",
        "pages_with_error",
        "records_collected",
        "unique_processes",
        "errors",
    )
    return (
        stored.id == incoming.id
        and stored.source == incoming.source
        and stored.status == incoming.status
        and stored.started_at == incoming.started_at
        and stored.ended_at == incoming.ended_at
        and all(
            getattr(stored.metrics, name) == getattr(incoming.metrics, name)
            for name in collection_metric_names
        )
    )
