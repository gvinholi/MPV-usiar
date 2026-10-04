"""Domínio: conceitos e regras de negócio.

Não realizar I/O neste pacote. Não importar `collector.infra` nem
`collector.application`. Não acoplar a fornecedor de banco, storage ou HTTP.
"""

from collector.domain.collection_round import CollectionRound, RoundStatus
from collector.domain.metrics import RoundMetrics
from collector.domain.process import Process
from collector.domain.screening import ScreeningStatus
from collector.domain.source import Source, SourceIdentity

__all__ = [
    "CollectionRound",
    "Process",
    "RoundMetrics",
    "RoundStatus",
    "ScreeningStatus",
    "Source",
    "SourceIdentity",
]
