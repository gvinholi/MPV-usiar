"""Configurable, disabled-by-default scheduler for three daily PNCP runs."""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, time
from time import sleep
from typing import Protocol

from collector.application import (
    CollectionRequest,
    DailyCollectionSchedule,
    OperationalRunAlreadyRunningError,
    OperationalRunSummary,
    RetryPolicy,
    ScreeningProfile,
    usiar_v2,
)
from collector.cli.collect import (
    EXIT_ALREADY_RUNNING,
    EXIT_FAILED,
    EXIT_PARTIAL,
    EXIT_SUCCESS,
    build_runner,
)

DEFAULT_TIMEZONE = "America/Sao_Paulo"
DEFAULT_TIMES = "06:00,12:00,18:00"
USIAR_V2_PROFILE_ID = "42227c23-f6ea-5a43-b640-56ed6eb6981c"


class SchedulerConfigError(ValueError):
    pass


class Runner(Protocol):
    def run(
        self, request: CollectionRequest, profile: ScreeningProfile
    ) -> OperationalRunSummary: ...


RunnerBuilder = Callable[["SchedulerConfig"], Runner]
Clock = Callable[[], datetime]
Sleeper = Callable[[float], None]


def _integer(
    raw: Mapping[str, str], name: str, default: int, minimum: int, maximum: int
) -> int:
    value = raw.get(name, str(default)).strip()
    try:
        parsed = int(value)
    except ValueError as exc:
        raise SchedulerConfigError(f"{name} deve ser inteiro") from exc
    if not minimum <= parsed <= maximum:
        raise SchedulerConfigError(f"{name} deve estar entre {minimum} e {maximum}")
    return parsed


def _number(
    raw: Mapping[str, str], name: str, default: float, minimum: float, maximum: float
) -> float:
    value = raw.get(name, str(default)).strip()
    try:
        parsed = float(value)
    except ValueError as exc:
        raise SchedulerConfigError(f"{name} deve ser numérico") from exc
    if not math.isfinite(parsed) or not minimum <= parsed <= maximum:
        raise SchedulerConfigError(f"{name} deve estar entre {minimum} e {maximum}")
    return parsed


def _enabled(raw: Mapping[str, str]) -> bool:
    value = raw.get("COLLECTION_SCHEDULER_ENABLED", "false").strip().lower()
    if value not in {"true", "false"}:
        raise SchedulerConfigError(
            "COLLECTION_SCHEDULER_ENABLED deve ser true ou false"
        )
    return value == "true"


def _times(value: str) -> tuple[time, ...]:
    parsed: list[time] = []
    for item in value.split(","):
        item = item.strip()
        if re.fullmatch(r"\d{2}:\d{2}", item) is None:
            raise SchedulerConfigError("COLLECTION_SCHEDULE_TIMES deve usar HH:MM")
        try:
            parsed.append(time.fromisoformat(item))
        except ValueError as exc:
            raise SchedulerConfigError(
                "COLLECTION_SCHEDULE_TIMES deve usar HH:MM"
            ) from exc
    return tuple(parsed)


def _modalities(value: str) -> tuple[int, ...]:
    if not value.strip():
        raise SchedulerConfigError("COLLECTION_MODALITIES é obrigatória")
    try:
        parsed = tuple(int(item.strip()) for item in value.split(","))
    except ValueError as exc:
        raise SchedulerConfigError(
            "COLLECTION_MODALITIES deve conter inteiros"
        ) from exc
    if any(item < 1 for item in parsed) or len(set(parsed)) != len(parsed):
        raise SchedulerConfigError(
            "COLLECTION_MODALITIES contém valor inválido ou duplicado"
        )
    return parsed


@dataclass(frozen=True)
class SchedulerConfig:
    enabled: bool
    schedule: DailyCollectionSchedule
    modalities: tuple[int, ...]
    uf: str
    page_size: int
    max_pages: int
    timeout_seconds: float
    retry_policy: RetryPolicy
    profile: str = "USIAR/v2"

    @classmethod
    def from_environment(cls, raw: Mapping[str, str]) -> "SchedulerConfig":
        if not raw.get("DATABASE_URL", "").strip():
            raise SchedulerConfigError("DATABASE_URL é obrigatória")
        timezone_name = raw.get("COLLECTION_TIMEZONE", DEFAULT_TIMEZONE).strip()
        window_days = _integer(raw, "COLLECTION_WINDOW_DAYS", 2, 1, 31)
        try:
            schedule = DailyCollectionSchedule(
                timezone_name,
                _times(raw.get("COLLECTION_SCHEDULE_TIMES", DEFAULT_TIMES)),
                window_days,
            )
        except ValueError as exc:
            raise SchedulerConfigError(str(exc)) from exc
        uf = raw.get("COLLECTION_UF", "SP").strip().upper()
        if uf != "SP":
            raise SchedulerConfigError("COLLECTION_UF deve ser SP neste MVP")
        profile = raw.get("COLLECTION_PROFILE", "USIAR/v2").strip()
        if profile != "USIAR/v2":
            raise SchedulerConfigError("COLLECTION_PROFILE deve ser USIAR/v2")
        retry_policy = RetryPolicy(
            max_attempts=_integer(raw, "COLLECTION_RETRY_ATTEMPTS", 3, 1, 10),
            initial_delay_seconds=_number(
                raw, "COLLECTION_RETRY_INITIAL_SECONDS", 0.5, 0, 60
            ),
            backoff_factor=_number(raw, "COLLECTION_RETRY_BACKOFF", 2.0, 1, 10),
            max_delay_seconds=_number(raw, "COLLECTION_RETRY_MAX_SECONDS", 8.0, 0, 300),
        )
        if retry_policy.max_delay_seconds < retry_policy.initial_delay_seconds:
            raise SchedulerConfigError(
                "COLLECTION_RETRY_MAX_SECONDS não pode ser menor que o atraso inicial"
            )
        return cls(
            enabled=_enabled(raw),
            schedule=schedule,
            modalities=_modalities(raw.get("COLLECTION_MODALITIES", "")),
            uf=uf,
            page_size=_integer(raw, "COLLECTION_PAGE_SIZE", 50, 10, 500),
            max_pages=_integer(raw, "COLLECTION_MAX_PAGES", 200, 2, 10_000),
            timeout_seconds=_number(raw, "COLLECTION_TIMEOUT_SECONDS", 30, 1, 300),
            retry_policy=retry_policy,
            profile=profile,
        )

    def safe_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "timezone": self.schedule.timezone_name,
            "times": [item.strftime("%H:%M") for item in self.schedule.run_times],
            "window_days": self.schedule.window_days,
            "modalities": list(self.modalities),
            "uf": self.uf,
            "page_size": self.page_size,
            "max_pages": self.max_pages,
            "timeout_seconds": self.timeout_seconds,
            "retry_attempts": self.retry_policy.max_attempts,
            "profile": self.profile,
            "profile_id": USIAR_V2_PROFILE_ID,
        }


def _build_runner(config: SchedulerConfig) -> Runner:
    return build_runner(
        config.max_pages,
        timeout_seconds=config.timeout_seconds,
        retry_policy=config.retry_policy,
    )


def _event(name: str, **fields: object) -> None:
    logging.getLogger(__name__).info(
        json.dumps({"event": name, **fields}, ensure_ascii=False, sort_keys=True)
    )


def execute_once(
    config: SchedulerConfig,
    runner: Runner,
    instant: datetime,
) -> tuple[int, OperationalRunSummary | None]:
    window = config.schedule.window_for(instant)
    _event(
        "scheduled_collection_started",
        scheduled_at=instant.astimezone(config.schedule.timezone).isoformat(),
        start_date=window.start_date.isoformat(),
        end_date=window.end_date.isoformat(),
        modalities=list(config.modalities),
        uf=config.uf,
        profile=config.profile,
    )
    try:
        summary = runner.run(
            CollectionRequest(
                start_date=window.start_date,
                end_date=window.end_date,
                modality_codes=config.modalities,
                uf=config.uf,
                page_size=config.page_size,
            ),
            usiar_v2(),
        )
    except OperationalRunAlreadyRunningError:
        _event("scheduled_collection_skipped", reason="already_running")
        return EXIT_ALREADY_RUNNING, None
    except Exception as exc:  # noqa: BLE001 - operational boundary sanitizes failures
        _event(
            "scheduled_collection_failed",
            error_code="RUN_FAILED",
            exception_type=type(exc).__name__,
        )
        return EXIT_FAILED, None
    _event("scheduled_collection_finished", **summary.as_dict())
    if summary.status == "SUCCESS":
        return EXIT_SUCCESS, summary
    if summary.status == "PARTIAL":
        return EXIT_PARTIAL, summary
    return EXIT_FAILED, summary


def run_daemon(
    config: SchedulerConfig,
    runner: Runner,
    *,
    clock: Clock,
    sleeper: Sleeper = sleep,
    max_runs: int | None = None,
) -> None:
    if max_runs is not None and max_runs < 1:
        raise ValueError("max_runs deve ser positivo")
    if not config.enabled:
        raise SchedulerConfigError(
            "scheduler desativado; defina COLLECTION_SCHEDULER_ENABLED=true somente após aprovação"
        )
    _event("collection_scheduler_started", **config.safe_dict())
    runs = 0
    while True:
        now = clock()
        next_run = config.schedule.next_after(now)
        _event("collection_scheduler_waiting", next_run=next_run.isoformat())
        sleeper(
            max(
                0.0,
                (next_run - now.astimezone(config.schedule.timezone)).total_seconds(),
            )
        )
        execute_once(config, runner, clock())
        runs += 1
        if max_runs is not None and runs >= max_runs:
            return


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Agenda três coletas PNCP diárias.")
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("show-config", help="Valida e exibe configuração sem segredos.")
    commands.add_parser("run-once", help="Executa agora uma janela configurada.")
    commands.add_parser("daemon", help="Aguarda e executa os três horários diários.")
    return result


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    runner_builder: RunnerBuilder = _build_runner,
    clock: Clock | None = None,
    sleeper: Sleeper = sleep,
) -> int:
    arguments = parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        config = SchedulerConfig.from_environment(
            environ if environ is not None else os.environ
        )
        if arguments.command == "show-config":
            print(json.dumps(config.safe_dict(), ensure_ascii=False, sort_keys=True))
            return EXIT_SUCCESS
        runner = runner_builder(config)
        current_clock = clock or (lambda: datetime.now(config.schedule.timezone))
        if arguments.command == "run-once":
            exit_code, summary = execute_once(config, runner, current_clock())
            if summary is not None:
                print(json.dumps(summary.as_dict(), ensure_ascii=False, sort_keys=True))
            return exit_code
        run_daemon(config, runner, clock=current_clock, sleeper=sleeper)
    except SchedulerConfigError as exc:
        logging.getLogger(__name__).error(
            json.dumps(
                {"event": "scheduler_configuration_invalid", "error": str(exc)},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2
    except KeyboardInterrupt:
        _event("collection_scheduler_stopped", reason="interrupt")
        return EXIT_SUCCESS
    except Exception as exc:  # noqa: BLE001 - startup boundary sanitizes configuration failures
        _event(
            "collection_scheduler_start_failed",
            error_code="START_FAILED",
            exception_type=type(exc).__name__,
        )
        return EXIT_FAILED
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
