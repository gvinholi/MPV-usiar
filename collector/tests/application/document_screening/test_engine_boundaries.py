"""O motor documental não conhece SQLAlchemy, IA nem termos USIAR hard-coded."""

from __future__ import annotations

import ast
from pathlib import Path

ENGINE_DIR = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "collector"
    / "application"
    / "document_screening"
)
FORBIDDEN_IMPORTS = ("collector.infra", "sqlalchemy", "openai", "httpx")
FORBIDDEN_TOKENS = (
    "openai",
    "embedding",
    "fuzzy",
    "levenshtein",
    "manutenção preventiva",
    "ar condicionado",
    "confidence",
)


def test_package_has_no_infra_or_ai_imports() -> None:
    imported: list[str] = []
    for path in ENGINE_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
    assert [name for name in imported if name.startswith(FORBIDDEN_IMPORTS)] == []


def test_engine_does_not_hardcode_usiar_terms_or_ai() -> None:
    text = (ENGINE_DIR / "engine.py").read_text(encoding="utf-8")
    assert [token for token in FORBIDDEN_TOKENS if token in text] == []


def test_decide_does_not_hardcode_usiar_terms() -> None:
    text = (ENGINE_DIR / "decide.py").read_text(encoding="utf-8")
    assert [token for token in FORBIDDEN_TOKENS if token in text] == []
