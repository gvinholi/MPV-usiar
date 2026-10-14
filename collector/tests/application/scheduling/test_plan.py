from datetime import date, datetime, time, timezone

import pytest

from collector.application import DailyCollectionSchedule


def _schedule(window_days=2):
    return DailyCollectionSchedule(
        "America/Sao_Paulo",
        (time(18), time(6), time(12)),
        window_days,
    )


def test_schedule_has_exactly_three_sorted_sao_paulo_occurrences():
    occurrences = _schedule().occurrences_on(date(2026, 10, 13))

    assert [item.isoformat() for item in occurrences] == [
        "2026-10-13T06:00:00-03:00",
        "2026-10-13T12:00:00-03:00",
        "2026-10-13T18:00:00-03:00",
    ]


def test_next_occurrence_handles_utc_and_day_rollover():
    schedule = _schedule()

    assert (
        schedule.next_after(datetime(2026, 10, 13, 14, tzinfo=timezone.utc)).isoformat()
        == "2026-10-13T12:00:00-03:00"
    )
    assert (
        schedule.next_after(datetime(2026, 10, 13, 22, tzinfo=timezone.utc)).isoformat()
        == "2026-10-14T06:00:00-03:00"
    )


def test_overlapping_window_recovers_dates_after_a_missed_round():
    schedule = _schedule(window_days=2)
    after_missed_noon_run = datetime.fromisoformat("2026-10-13T18:00:00-03:00")

    window = schedule.window_for(after_missed_noon_run)

    assert window.start_date == date(2026, 10, 12)
    assert window.end_date == date(2026, 10, 13)


@pytest.mark.parametrize(
    "times",
    [
        (time(6), time(12)),
        (time(6), time(6), time(18)),
        (time(6, 0, 1), time(12), time(18)),
    ],
)
def test_schedule_rejects_invalid_daily_occurrences(times):
    with pytest.raises(ValueError):
        DailyCollectionSchedule("America/Sao_Paulo", times)


def test_schedule_requires_aware_instants_and_known_timezone():
    with pytest.raises(ValueError, match="timezone"):
        DailyCollectionSchedule("Invalid/Timezone", (time(6), time(12), time(18)))
    with pytest.raises(ValueError, match="fuso"):
        _schedule().next_after(datetime(2026, 10, 13, 12))
