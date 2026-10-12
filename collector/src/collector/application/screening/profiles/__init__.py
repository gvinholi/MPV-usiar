"""Perfis concretos. O motor não depende deste pacote."""

from collector.application.screening.profiles.usiar import (
    USIAR_V1_ID,
    USIAR_V2_ID,
    usiar_v1,
    usiar_v2,
)

__all__ = ["USIAR_V1_ID", "USIAR_V2_ID", "usiar_v1", "usiar_v2"]
