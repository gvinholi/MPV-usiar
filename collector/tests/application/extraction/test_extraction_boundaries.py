"""Extração na aplicação sem USIAR e sem pypdf."""

from pathlib import Path

ROOT = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "collector"
    / "application"
    / "extraction"
)
FORBIDDEN = ("USIAR", "CANDIDATE", "PENDING", "DISCARDED", "pypdf", "Tesseract", "OpenAI")


def test_application_extraction_has_no_usiar_or_pypdf() -> None:
    for path in ROOT.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN:
            assert token not in text, f"{path.name} contém {token}"
