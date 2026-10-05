"""Aquisição sem regras USIAR e sem SQLAlchemy/httpx na aplicação."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / "src" / "collector" / "application" / "acquisition"
FORBIDDEN = ("USIAR", "CANDIDATE", "PENDING", "DISCARDED")


def test_acquisition_application_has_no_usiar_or_httpx() -> None:
    for path in ROOT.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN:
            assert token not in text, f"{path.name} contém {token}"
