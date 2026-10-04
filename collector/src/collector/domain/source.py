"""Origem de uma publicação ou processo.

Enum é suficiente neste estágio: o conjunto de fontes é fechado e novas
fontes só entram como membros quando o acesso for aprovado. Não usar
strings soltas como identificador de fonte.
"""

from dataclasses import dataclass
from enum import Enum


class Source(Enum):
    PNCP = "PNCP"
    RHS = "RHS"


@dataclass(frozen=True)
class SourceIdentity:
    """Identidade oficial de um processo em uma fonte.

    O identificador oficial é o da fonte, não o título nem o número
    visível do edital. Várias identidades podem coexistir no mesmo
    processo interno para fontes distintas.
    """

    source: Source
    official_id: str

    def __post_init__(self) -> None:
        official_id = self.official_id.strip()
        if not official_id:
            raise ValueError("id oficial da fonte é obrigatório")
        object.__setattr__(self, "official_id", official_id)
