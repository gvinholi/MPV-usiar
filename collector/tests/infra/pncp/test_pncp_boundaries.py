"""O cliente HTTP PNCP não importa domínio. Só o fetcher implementa a porta de aplicação."""

from __future__ import annotations

import ast
from pathlib import Path

PNCP_ROOT = (
    Path(__file__).resolve().parents[3] / "src" / "collector" / "infra" / "pncp"
)
HTTP_MODULES = {"client.py", "errors.py", "models.py"}


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    return imported


def test_pncp_non_mapper_modules_do_not_import_domain() -> None:
    violations: list[str] = []
    for path in sorted(PNCP_ROOT.rglob("*.py")):
        if path.name in {"mapper.py", "publication_mapper.py"}:
            continue
        for module in _imported_modules(path):
            if module.startswith("collector.domain"):
                violations.append(f"{path.relative_to(PNCP_ROOT)}: importa {module}")
    assert violations == []


def test_pncp_http_modules_do_not_import_application() -> None:
    violations: list[str] = []
    for path in sorted(PNCP_ROOT.rglob("*.py")):
        if path.name not in HTTP_MODULES:
            continue
        for module in _imported_modules(path):
            if module.startswith("collector.application"):
                violations.append(f"{path.relative_to(PNCP_ROOT)}: importa {module}")
    assert violations == []
