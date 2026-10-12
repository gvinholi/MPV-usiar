"""CLI explícito para uma rodada operacional do PNCP."""

from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Callable, Sequence
from datetime import date

from collector.application import (
    CollectionOrchestrator,
    CollectionRequest,
    OperationalCollectionRunner,
    PersistCollection,
    PersistOperationalResolution,
    PersistScreening,
    PublicationPaginator,
    usiar_v1,
    usiar_v2,
)
from collector.infra.database import (
    SqlAlchemyCollectionRepository,
    SqlAlchemyOperationalResolutionRepository,
    SqlAlchemyOperationalRunRepository,
    SqlAlchemyScreeningRepository,
    create_session_factory,
)
from collector.infra.pncp import (
    PncpClient,
    PncpPublicationFetcher,
    PncpPublicationMapper,
)

RunnerFactory = Callable[[int], OperationalCollectionRunner]
EXIT_SUCCESS = 0
EXIT_FAILED = 1
EXIT_PARTIAL = 3


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use data no formato YYYY-MM-DD") from exc


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use um número inteiro") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("o valor deve ser maior ou igual a 1")
    return parsed


def _uf(value: str) -> str:
    normalized = value.strip().upper()
    if len(normalized) != 2 or not normalized.isalpha():
        raise argparse.ArgumentTypeError("UF deve conter exatamente duas letras")
    return normalized


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Executa uma rodada operacional de coleta PNCP."
    )
    commands = result.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Coleta, persiste e classifica uma rodada.")
    run.add_argument("--start-date", required=True, type=_date)
    run.add_argument("--end-date", required=True, type=_date)
    run.add_argument(
        "--uf",
        required=True,
        type=_uf,
        help="UF explícita; omissão não dispara coleta nacional.",
    )
    run.add_argument(
        "--modality",
        required=True,
        action="append",
        type=_positive_int,
        dest="modalities",
        help="Código PNCP. Repita a opção para múltiplas modalidades.",
    )
    run.add_argument(
        "--profile", choices=("USIAR/v1", "USIAR/v2"), default="USIAR/v1"
    )
    run.add_argument(
        "--page-size",
        type=_positive_int,
        help="Tamanho solicitado ao PNCP; sem limite de teste implícito.",
    )
    run.add_argument(
        "--max-pages",
        type=_positive_int,
        default=200,
        help="Limite de segurança explícito por modalidade (padrão: 200).",
    )
    return result


def build_runner(max_pages: int) -> OperationalCollectionRunner:
    session_factory = create_session_factory()
    collector = CollectionOrchestrator(
        PublicationPaginator(PncpPublicationFetcher(PncpClient()), max_pages=max_pages),
        PncpPublicationMapper(),
    )
    return OperationalCollectionRunner(
        collector,
        PersistCollection(SqlAlchemyCollectionRepository(session_factory)),
        PersistScreening(SqlAlchemyScreeningRepository(session_factory)),
        PersistOperationalResolution(
            SqlAlchemyOperationalResolutionRepository(session_factory)
        ),
        SqlAlchemyOperationalRunRepository(session_factory),
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    runner_factory: RunnerFactory = build_runner,
) -> int:
    arguments = parser().parse_args(argv)
    if arguments.command != "run":
        return 2
    if arguments.end_date < arguments.start_date:
        parser().error("--end-date não pode ser anterior a --start-date")
    if len(set(arguments.modalities)) != len(arguments.modalities):
        parser().error("--modality não pode conter códigos duplicados")

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        runner = runner_factory(arguments.max_pages)
        summary = runner.run(
            CollectionRequest(
                start_date=arguments.start_date,
                end_date=arguments.end_date,
                modality_codes=tuple(arguments.modalities),
                uf=arguments.uf,
                page_size=arguments.page_size,
            ),
            {"USIAR/v1": usiar_v1, "USIAR/v2": usiar_v2}[arguments.profile](),
        )
    except Exception as exc:  # noqa: BLE001 - CLI sanitiza a falha operacional
        logging.getLogger(__name__).error(
            json.dumps(
                {
                    "event": "operational_run_failed",
                    "error_code": "RUN_FAILED",
                    "exception_type": type(exc).__name__,
                },
                sort_keys=True,
            )
        )
        return 1

    print(json.dumps(summary.as_dict(), ensure_ascii=False, sort_keys=True))
    if summary.status == "SUCCESS":
        return EXIT_SUCCESS
    if summary.status == "PARTIAL":
        return EXIT_PARTIAL
    return EXIT_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
