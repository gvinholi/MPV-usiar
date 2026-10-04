"""Estados do funil de triagem.

As regras que decidem a transição (perfil USIAR) não pertencem a este
módulo. Motivo de descarte ou pendência é armazenado no processo.
"""

from enum import Enum


class ScreeningStatus(Enum):
    RAW = "RAW"
    UNIQUE = "UNIQUE"
    CANDIDATE = "CANDIDATE"
    SELECTED = "SELECTED"
    PENDING = "PENDING"
    DISCARDED = "DISCARDED"
    CONFIRMED = "CONFIRMED"
