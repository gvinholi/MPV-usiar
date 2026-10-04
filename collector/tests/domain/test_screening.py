"""Estados do funil de triagem, sem regras USIAR."""

from collector.domain import ScreeningStatus


def test_screening_status_covers_funnel() -> None:
    assert {item for item in ScreeningStatus} == {
        ScreeningStatus.RAW,
        ScreeningStatus.UNIQUE,
        ScreeningStatus.CANDIDATE,
        ScreeningStatus.SELECTED,
        ScreeningStatus.PENDING,
        ScreeningStatus.DISCARDED,
        ScreeningStatus.CONFIRMED,
    }
