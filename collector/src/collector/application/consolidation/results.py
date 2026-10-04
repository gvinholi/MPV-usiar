"""Visão auditável da consolidação: observações × processos únicos."""

from __future__ import annotations

from dataclasses import dataclass

from collector.domain import Process, SourceIdentity


@dataclass(frozen=True)
class ConsolidatedProcess:
    process: Process
    identities: tuple[SourceIdentity, ...]
    observations: tuple[Process, ...]
    observation_count: int


@dataclass(frozen=True)
class ConsolidationResult:
    observations_received: int
    unique_processes: int
    duplicates: int
    groups: tuple[ConsolidatedProcess, ...]
