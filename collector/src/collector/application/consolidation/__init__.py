"""Consolidação de observações em processos únicos por identidade exata."""

from collector.application.consolidation.consolidator import ProcessConsolidator
from collector.application.consolidation.errors import ConsolidationError
from collector.application.consolidation.results import (
    ConsolidatedProcess,
    ConsolidationResult,
)

__all__ = [
    "ConsolidatedProcess",
    "ConsolidationError",
    "ConsolidationResult",
    "ProcessConsolidator",
]
