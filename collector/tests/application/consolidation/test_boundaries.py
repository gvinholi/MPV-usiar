"""O consolidador não conhece PNCP nem persiste."""

from __future__ import annotations

import ast
from pathlib import Path

CONSOLIDATION_ROOT = (
    Path(__file__).resolve().parents[3] / "src" / "collector" / "application" / "consolidation"
)
FORBIDDEN_PREFIXES = ("collector.infra", "httpx", "sqlalchemy", "psycopg")
FORBIDDEN_TOKENS = (
    "numeroControlePNCP",
    "fuzzy",
    "levenshtein",
    "CREATE TABLE",
    "INSERT INTO",
)


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    return imported


def test_consolidation_does_not_import_infra_or_persistence() -> None:
    violations: list[str] = []
    for path in sorted(CONSOLIDATION_ROOT.rglob("*.py")):
        for module in _imported_modules(path):
            if module.startswith(FORBIDDEN_PREFIXES):
                violations.append(f"{path.name}: importa {module}")
    assert violations == []


def test_consolidation_has_no_pncp_or_fuzzy_or_sql() -> None:
    violations: list[str] = []
    for path in sorted(CONSOLIDATION_ROOT.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_TOKENS:
            if token in text:
                violations.append(f"{path.name}: {token}")
    assert violations == []
