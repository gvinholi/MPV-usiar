from __future__ import annotations

import json
from uuid import uuid4

import pytest

from collector.application import (
    OperationalRunAlreadyRunningError,
    OperationalRunSummary,
)
from collector.cli.collect import EXIT_ALREADY_RUNNING, main


class StubRunner:
    def __init__(self, status="SUCCESS"):
        self.calls = []
        self.status = status

    def run(self, request, profile):
        self.calls.append((request, profile))
        return OperationalRunSummary(
            round_id=uuid4(),
            status=self.status,
            requested_modalities=(6, 8),
            completed_modalities=(6, 8),
            incomplete_modalities=(),
            records_collected=3,
            processes_mapped=3,
            unique_processes=2,
            processes_created=2,
            observations_created=2,
            evaluations_created=2,
            resolutions_created=2,
            candidates=1,
            pending=1,
            discarded=0,
            errors=0,
        )


def test_cli_executes_real_command_contract_and_prints_json(capsys):
    runner = StubRunner()
    limits = []

    def factory(max_pages):
        limits.append(max_pages)
        return runner

    exit_code = main(
        [
            "run",
            "--start-date",
            "2026-10-01",
            "--end-date",
            "2026-10-02",
            "--uf",
            "sp",
            "--modality",
            "6",
            "--modality",
            "8",
            "--page-size",
            "25",
            "--max-pages",
            "2",
        ],
        runner_factory=factory,
    )

    assert exit_code == 0
    assert limits == [2]
    request, profile = runner.calls[0]
    assert request.uf == "SP"
    assert request.modality_codes == (6, 8)
    assert request.page_size == 25
    assert profile.identity == "USIAR/v1"
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "SUCCESS"
    assert payload["round_id"]


def test_cli_rejects_national_run_and_duplicate_modalities():
    with pytest.raises(SystemExit) as missing_uf:
        main(
            [
                "run",
                "--start-date",
                "2026-10-01",
                "--end-date",
                "2026-10-01",
                "--modality",
                "6",
            ]
        )
    assert missing_uf.value.code == 2

    with pytest.raises(SystemExit) as duplicate:
        main(
            [
                "run",
                "--start-date",
                "2026-10-01",
                "--end-date",
                "2026-10-01",
                "--uf",
                "SP",
                "--modality",
                "6",
                "--modality",
                "6",
            ]
        )
    assert duplicate.value.code == 2


def test_cli_sanitizes_operational_failure(capsys):
    class FailingRunner:
        def run(self, _request, _profile):
            raise RuntimeError("secret database details")

    exit_code = main(
        [
            "run",
            "--start-date",
            "2026-10-01",
            "--end-date",
            "2026-10-01",
            "--uf",
            "SP",
            "--modality",
            "6",
        ],
        runner_factory=lambda _max_pages: FailingRunner(),
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "secret database details" not in captured.err


def test_cli_returns_distinct_code_when_shared_lock_is_busy(caplog):
    class BusyRunner:
        def run(self, _request, _profile):
            raise OperationalRunAlreadyRunningError("internal lock detail")

    exit_code = main(
        [
            "run",
            "--start-date",
            "2026-10-01",
            "--end-date",
            "2026-10-01",
            "--uf",
            "SP",
            "--modality",
            "6",
        ],
        runner_factory=lambda _max_pages: BusyRunner(),
    )

    assert exit_code == EXIT_ALREADY_RUNNING
    assert "already_running" in caplog.text
    assert "internal lock detail" not in caplog.text


def test_cli_selects_usiar_v2_explicitly(capsys):
    runner = StubRunner()

    exit_code = main(
        [
            "run",
            "--start-date",
            "2026-10-01",
            "--end-date",
            "2026-10-01",
            "--uf",
            "SP",
            "--modality",
            "6",
            "--profile",
            "USIAR/v2",
        ],
        runner_factory=lambda _max_pages: runner,
    )

    assert exit_code == 0
    assert runner.calls[0][1].identity == "USIAR/v2"
    assert json.loads(capsys.readouterr().out)["status"] == "SUCCESS"


@pytest.mark.parametrize(
    ("status", "expected_exit_code"),
    (("SUCCESS", 0), ("FAILED", 1), ("PARTIAL", 3)),
)
def test_cli_exit_code_represents_round_status(status, expected_exit_code, capsys):
    runner = StubRunner(status)

    exit_code = main(
        [
            "run",
            "--start-date",
            "2026-10-01",
            "--end-date",
            "2026-10-01",
            "--uf",
            "SP",
            "--modality",
            "6",
        ],
        runner_factory=lambda _max_pages: runner,
    )

    assert exit_code == expected_exit_code
    assert json.loads(capsys.readouterr().out)["status"] == status
