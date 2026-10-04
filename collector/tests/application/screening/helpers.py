"""Atalhos de avaliação para testes."""

from uuid import uuid4

from collector.application.screening import ScreeningEngine, ScreeningEvaluation, ScreeningProfile, usiar_v1


def screen(
    description: str | None,
    profile: ScreeningProfile | None = None,
    *,
    engine: ScreeningEngine | None = None,
) -> ScreeningEvaluation:
    return (engine or ScreeningEngine()).evaluate(
        profile or usiar_v1(),
        description=description,
        process_id=uuid4(),
        observation_id=uuid4(),
    )
