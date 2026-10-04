"""A aplicação não depende de infra concreta nem de httpx."""

from __future__ import annotations

import ast
from pathlib import Path

APPLICATION_ROOT = Path(__file__).resolve().parents[2] / "src" / "collector" / "application"
FORBIDDEN_PREFIXES = ("collector.infra", "httpx")


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    return imported


def test_application_does_not_import_infra_or_httpx() -> None:
    violations: list[str] = []
    for path in sorted(APPLICATION_ROOT.rglob("*.py")):
        for module in _imported_modules(path):
            if module.startswith(FORBIDDEN_PREFIXES):
                violations.append(f"{path.relative_to(APPLICATION_ROOT)}: importa {module}")
    assert violations == []
