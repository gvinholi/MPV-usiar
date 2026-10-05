"""Catálogo e cliente de documentos sem USIAR e sem SQLAlchemy na aplicação."""

from __future__ import annotations

from pathlib import Path

PNCP = Path(__file__).resolve().parents[3] / "src" / "collector" / "infra" / "pncp"
FORBIDDEN = ("USIAR", "manutenção", "CANDIDATE", "PENDING", "DISCARDED")


def test_document_client_and_mapper_have_no_usiar_rules() -> None:
    for name in ("document_client.py", "document_mapper.py", "document_fetcher.py"):
        text = (PNCP / name).read_text(encoding="utf-8")
        for token in FORBIDDEN:
            assert token not in text, f"{name} contém {token}"
