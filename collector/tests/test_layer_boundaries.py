"""Garante que o domínio não depende de aplicação nem de infraestrutura."""

from __future__ import annotations

import ast
from pathlib import Path

DOMAIN_ROOT = Path(__file__).resolve().parents[1] / "src" / "collector" / "domain"
FORBIDDEN_PREFIXES = ("collector.infra", "collector.application")


def _python_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def test_domain_does_not_import_application_or_infra() -> None:
    violations: list[str] = []
    for path in _python_files(DOMAIN_ROOT):
        for module in _imported_modules(path):
            if module.startswith(FORBIDDEN_PREFIXES):
                relative = path.relative_to(DOMAIN_ROOT)
                violations.append(f"{relative}: importa {module}")
    assert violations == []
