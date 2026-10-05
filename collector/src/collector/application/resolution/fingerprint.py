"""Identidades lógicas da resolução. Sem UUID de row e sem timestamp."""

from __future__ import annotations

import hashlib

from collector.application.document_screening.results import DocumentScreeningEvaluation
from collector.application.screening.results import ScreeningEvaluation

RESOLVER_ENGINE_VERSION = "1"


def initial_input_fingerprint(evaluation: ScreeningEvaluation) -> str:
    """Identidade do sinal analisado na triagem inicial.

    Não usa `evaluation.id`. Usa perfil, engine, campo, estado, reason e
    evidências ordenadas — o conteúdo efetivamente considerado. O FK
    histórico aponta para a row; o fingerprint lógico não.
    """

    lines = [
        f"{evaluation.profile_code}/{evaluation.profile_version}",
        evaluation.engine_version,
        evaluation.field,
        evaluation.state.value,
        evaluation.reason_code.value,
        *[
            f"{item.category}\t{item.configured_term}\t{item.field}\t{item.matched_text}"
            for item in sorted(
                evaluation.evidence,
                key=lambda item: (item.category, item.configured_term, item.matched_text),
            )
        ],
    ]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def resolution_fingerprint(
    initial: ScreeningEvaluation,
    document: DocumentScreeningEvaluation | None,
    *,
    resolver_version: str = RESOLVER_ENGINE_VERSION,
) -> str:
    document_token = (
        "NONE" if document is None else document.document_set_fingerprint
    )
    payload = "\n".join(
        (
            f"{initial.profile_code}/{initial.profile_version}",
            resolver_version,
            f"initial:{initial_input_fingerprint(initial)}",
            f"document:{document_token}",
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
