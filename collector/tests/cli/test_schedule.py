from __future__ import annotations

import json
import logging
from datetime import datetime
from uuid import uuid4

import pytest

from collector.application import OperationalRunSummary
from collector.application.screening import USIAR_V2_ID
from collector.cli.schedule import SchedulerConfig, execute_once, main, run_daemon


def _environment(**overrides):
    values = {
        "DATABASE_URL": "postgresql+psycopg://user:secret@db.example/usiar",
        "COLLECTION_MODALITIES": "6,8",
    }
    values.update(overrides)
    return values


class StubRunner:
    def __init__(self, status="SUCCESS"):
        self.status = status
        self.calls = []

    def run(self, request, profile):
        self.calls.append((request, profile))
        return OperationalRunSummary(
            round_id=uuid4(),
            status=self.status,
            requested_modalities=request.modality_codes,
            completed_modalities=request.modality_codes
            if self.status == "SUCCESS"
            else (),
            incomplete_modalities=()
            if self.status == "SUCCESS"
            else request.modality_codes,
            records_collected=2,
            processes_mapped=2,
            unique_processes=2,
            processes_created=2,
            observations_created=2,
            evaluations_created=2,
            resolutions_created=2,
            candidates=1,
            pending=1,
            discarded=0,
            errors=0 if self.status == "SUCCESS" else 1,
            pages_processed=2,
            page_errors=0 if self.status == "SUCCESS" else 1,
        )


def test_config_defaults_are_safe_explicit_and_disabled():
    config = SchedulerConfig.from_environment(_environment())

    assert config.enabled is False
    assert config.schedule.timezone_name == "America/Sao_Paulo"
    assert [item.strftime("%H:%M") for item in config.schedule.run_times] == [
        "06:00",
        "12:00",
        "18:00",
    ]
    assert config.schedule.window_days == 2
    assert config.modalities == (6, 8)
    assert config.uf == "SP"
    assert config.profile == "USIAR/v2"
    assert config.max_pages == 200


def test_run_once_uses_overlapping_window_and_usiar_v2(capsys):
    runner = StubRunner()
    instant = datetime.fromisoformat("2026-10-13T06:00:00-03:00")

    exit_code = main(
        ["run-once"],
        environ=_environment(COLLECTION_PAGE_SIZE="25"),
        runner_builder=lambda _config: runner,
        clock=lambda: instant,
    )

    assert exit_code == 0
    request, profile = runner.calls[0]
    assert request.start_date.isoformat() == "2026-10-12"
    assert request.end_date.isoformat() == "2026-10-13"
    assert request.modality_codes == (6, 8)
    assert request.page_size == 25
    assert profile.id == USIAR_V2_ID
    assert json.loads(capsys.readouterr().out)["status"] == "SUCCESS"


@pytest.mark.parametrize(("status", "expected"), [("PARTIAL", 3), ("FAILED", 1)])
def test_run_once_preserves_non_success_status(status, expected):
    config = SchedulerConfig.from_environment(_environment())

    exit_code, summary = execute_once(
        config,
        StubRunner(status),
        datetime.fromisoformat("2026-10-13T12:00:00-03:00"),
    )

    assert exit_code == expected
    assert summary is not None and summary.status == status


def test_show_config_never_prints_database_url_or_password(capsys):
    assert main(["show-config"], environ=_environment()) == 0

    output = capsys.readouterr().out
    assert "postgresql" not in output
    assert "secret" not in output
    assert "42227c23-f6ea-5a43-b640-56ed6eb6981c" in output


def test_runner_startup_failure_is_sanitized(caplog):
    caplog.set_level(logging.INFO)

    def fail(_config):
        raise RuntimeError("postgresql://secret-user:secret-password@internal/db")

    assert main(["run-once"], environ=_environment(), runner_builder=fail) == 1
    assert "RuntimeError" in caplog.text
    assert "secret-password" not in caplog.text


def test_daemon_remains_disabled_until_explicit_approval(caplog):
    exit_code = main(
        ["daemon"],
        environ=_environment(),
        runner_builder=lambda _config: StubRunner(),
    )

    assert exit_code == 2
    assert "scheduler desativado" in caplog.text


def test_enabled_daemon_executes_three_server_side_runs():
    config = SchedulerConfig.from_environment(
        _environment(COLLECTION_SCHEDULER_ENABLED="true")
    )
    runner = StubRunner()
    instants = iter(
        datetime.fromisoformat(value)
        for value in (
            "2026-10-13T05:59:00-03:00",
            "2026-10-13T06:00:00-03:00",
            "2026-10-13T06:01:00-03:00",
            "2026-10-13T12:00:00-03:00",
            "2026-10-13T12:01:00-03:00",
            "2026-10-13T18:00:00-03:00",
        )
    )
    delays = []

    run_daemon(
        config,
        runner,
        clock=lambda: next(instants),
        sleeper=delays.append,
        max_runs=3,
    )

    assert len(runner.calls) == 3
    assert delays == [60.0, 21_540.0, 21_540.0]


@pytest.mark.parametrize(
    "override",
    [
        {"DATABASE_URL": ""},
        {"COLLECTION_MODALITIES": ""},
        {"COLLECTION_MODALITIES": "6,6"},
        {"COLLECTION_SCHEDULE_TIMES": "06:00,12:00"},
        {"COLLECTION_SCHEDULE_TIMES": "6:00,12:00,18:00"},
        {"COLLECTION_TIMEZONE": "Invalid/Timezone"},
        {"COLLECTION_UF": "RJ"},
        {"COLLECTION_PROFILE": "USIAR/v1"},
        {"COLLECTION_MAX_PAGES": "1"},
        {"COLLECTION_PAGE_SIZE": "9"},
        {"COLLECTION_RETRY_ATTEMPTS": "0"},
        {"COLLECTION_TIMEOUT_SECONDS": "0"},
        {"COLLECTION_SCHEDULER_ENABLED": "yes"},
    ],
)
def test_invalid_configuration_fails_before_runner_is_built(override):
    built = []

    exit_code = main(
        ["run-once"],
        environ=_environment(**override),
        runner_builder=lambda config: built.append(config),
    )

    assert exit_code == 2
    assert built == []
