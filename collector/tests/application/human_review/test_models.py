from dataclasses import replace
from uuid import uuid4

import pytest

from collector.application.human_review import (
    HumanReviewDecision as D, HumanReviewReason as R, HumanReviewStatus as S,
    RecordHumanReviewCommand, ReviewerIdentity, StaleOperationalResolutionError,
    RecordHumanReview,
)
from collector.application.human_review.models import ALLOWED_REASONS, check_stale, derive_status


def command(**kwargs):
    fields = dict(operational_resolution_id=uuid4(), reviewer=ReviewerIdentity("gabriel"),
                  decision=D.SELECTED, reason=R.TECHNICAL_FIT, idempotency_key="request-1")
    fields.update(kwargs)
    return RecordHumanReviewCommand(**fields)


@pytest.mark.parametrize("decision,reason", [(d, r) for d, reasons in ALLOWED_REASONS.items() for r in reasons])
def test_allowed_reasons(decision, reason):
    assert command(decision=decision, reason=reason, comment="justification").reason == reason


@pytest.mark.parametrize("kwargs", [
    dict(reason=R.OUT_OF_SCOPE), dict(decision=D.DISCARDED, reason=R.TECHNICAL_FIT),
    dict(decision=D.PENDING, reason=R.OTHER),
    dict(decision=D.PENDING, reason=R.OTHER, comment=" \n\t"),
    dict(comment="x" * 4001), dict(idempotency_key=" "), dict(idempotency_key="x" * 201),
    dict(decision="CONFIRMED"), dict(decision="CANDIDATE"), dict(allow_stale="true"),
])
def test_invalid_commands(kwargs):
    with pytest.raises(ValueError):
        command(**kwargs)


@pytest.mark.parametrize("reviewer", ["", " \n", "x" * 201])
def test_invalid_reviewer(reviewer):
    with pytest.raises(ValueError):
        ReviewerIdentity(reviewer)


def test_comment_boundary():
    assert len(command(comment="x" * 4000).comment) == 4000


def test_stale_policy():
    cmd = command()
    latest = uuid4()
    assert check_stale(cmd, cmd.operational_resolution_id) is False
    with pytest.raises(StaleOperationalResolutionError) as error:
        check_stale(cmd, latest)
    assert error.value.reviewed_resolution_id == cmd.operational_resolution_id
    assert error.value.latest_resolution_id == latest
    assert check_stale(replace(cmd, allow_stale=True), latest) is True


def test_status():
    assert derive_status(False, False) == S.UNREVIEWED
    assert derive_status(False, True) == S.STALE
    assert derive_status(True, True) == S.REVIEWED


def test_service_passes_clock_and_command_to_atomic_port():
    class Fake:
        def record(self, cmd, *, clock):
            assert cmd is requested
            assert clock() == "controlled"
            return "saved"
    requested = command()
    assert RecordHumanReview(Fake(), clock=lambda: "controlled").execute(requested) == "saved"


def test_human_module_has_no_infrastructure_imports():
    import ast
    from pathlib import Path
    import collector.application.human_review as module
    for path in Path(module.__file__).parent.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            modules = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            assert not any(m.startswith(("sqlalchemy", "collector.infra")) for m in modules)
