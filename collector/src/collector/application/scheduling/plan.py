"""Timezone-aware daily occurrences and overlapping publication windows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True)
class CollectionWindow:
    start_date: date
    end_date: date


@dataclass(frozen=True)
class DailyCollectionSchedule:
    timezone_name: str
    run_times: tuple[time, ...]
    window_days: int = 2

    def __post_init__(self) -> None:
        try:
            ZoneInfo(self.timezone_name)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("timezone inválido") from exc
        normalized = tuple(sorted(self.run_times))
        if len(normalized) != 3 or len(set(normalized)) != 3:
            raise ValueError("configure exatamente três horários distintos")
        if any(
            item.tzinfo is not None or item.second or item.microsecond
            for item in normalized
        ):
            raise ValueError("horários devem usar precisão de minuto sem fuso próprio")
        if not 1 <= self.window_days <= 31:
            raise ValueError("window_days deve estar entre 1 e 31")
        object.__setattr__(self, "run_times", normalized)

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone_name)

    def occurrences_on(self, local_date: date) -> tuple[datetime, ...]:
        return tuple(
            datetime.combine(local_date, item, self.timezone) for item in self.run_times
        )

    def next_after(self, instant: datetime) -> datetime:
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError("instant deve possuir fuso")
        local = instant.astimezone(self.timezone)
        for occurrence in self.occurrences_on(local.date()):
            if occurrence > local:
                return occurrence
        return self.occurrences_on(local.date() + timedelta(days=1))[0]

    def window_for(self, instant: datetime) -> CollectionWindow:
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError("instant deve possuir fuso")
        end_date = instant.astimezone(self.timezone).date()
        return CollectionWindow(
            start_date=end_date - timedelta(days=self.window_days - 1),
            end_date=end_date,
        )
