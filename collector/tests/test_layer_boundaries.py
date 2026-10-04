"""Garante que o domínio não depende de aplicação nem de infraestrutura."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

DOMAIN_ROOT = Path(__file__).resolve().parents[1] / "src" / "collector" / "domain"
FORBIDDEN_PREFIXES = ("collector.infra", "collector.application")


def _python_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def _imported_modules(path: Path) -> list[tuple[str, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend((alias.name, 0) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append((node.module, node.level))
    return imported


def test_domain_does_not_import_application_or_infra() -> None:
    violations: list[str] = []
    for path in _python_files(DOMAIN_ROOT):
        for module, _level in _imported_modules(path):
            if module.startswith(FORBIDDEN_PREFIXES):
                relative = path.relative_to(DOMAIN_ROOT)
                violations.append(f"{relative}: importa {module}")
    assert violations == []


PNCP_FIELD_NAMES = (
    "numeroControlePNCP",
    "orgaoEntidade",
    "dataPublicacaoPncp",
    "objetoCompra",
    "valorTotalEstimado",
)


def test_domain_does_not_mention_pncp_field_names() -> None:
    violations: list[str] = []
    for path in _python_files(DOMAIN_ROOT):
        text = path.read_text(encoding="utf-8")
        for name in PNCP_FIELD_NAMES:
            if name in text:
                violations.append(f"{path.relative_to(DOMAIN_ROOT)}: {name}")
    assert violations == []


def test_domain_imports_only_stdlib_and_own_package() -> None:
    allowed_roots = set(sys.stdlib_module_names) | {"collector"}
    violations: list[str] = []
    for path in _python_files(DOMAIN_ROOT):
        for module, level in _imported_modules(path):
            if level > 0:
                continue
            root = module.split(".", 1)[0]
            if root not in allowed_roots:
                relative = path.relative_to(DOMAIN_ROOT)
                violations.append(f"{relative}: importa {module}")
            elif root == "collector" and not module.startswith("collector.domain"):
                relative = path.relative_to(DOMAIN_ROOT)
                violations.append(f"{relative}: importa {module}")
    assert violations == []
