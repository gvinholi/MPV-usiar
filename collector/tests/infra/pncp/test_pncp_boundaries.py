"""O adaptador PNCP não importa o domínio nem a aplicação."""

from __future__ import annotations

import ast
from pathlib import Path

PNCP_ROOT = (
    Path(__file__).resolve().parents[3] / "src" / "collector" / "infra" / "pncp"
)
FORBIDDEN_PREFIXES = ("collector.domain", "collector.application")


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    return imported


def test_pncp_adapter_does_not_import_domain_or_application() -> None:
    violations: list[str] = []
    for path in sorted(PNCP_ROOT.rglob("*.py")):
        for module in _imported_modules(path):
            if module.startswith(FORBIDDEN_PREFIXES):
                violations.append(f"{path.relative_to(PNCP_ROOT)}: importa {module}")
    assert violations == []
