"""Conversão de datetimes do PNCP.

O manual oficial documenta dataAberturaProposta e dataEncerramentoProposta
como horário de Brasília. As demais strings do mesmo endpoint chegam no
mesmo formato, sem offset. Strings sem offset usam UTC−03:00
(horário oficial de Brasília; sem horário de verão desde 2019), não
porque a consulta tenha UF=SP. Offset explícito, quando presente, é
preservado.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from collector.infra.pncp.errors import PncpInvalidDateError, PncpInvalidTypeError

# Horário oficial de Brasília (manual PNCP). Sem horário de verão desde 2019.
# UTC−03:00 evita a dependência de tzdata no Windows.
PNCP_CIVIL_TIMEZONE = timezone(timedelta(hours=-3), name="UTC-03")


def parse_pncp_datetime(value: object, *, field: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PncpInvalidTypeError(
            f"{field} deve ser string", field=field
        )
    text = value.strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise PncpInvalidDateError(f"{field} não é uma data/hora válida", field=field) from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=PNCP_CIVIL_TIMEZONE)
    return parsed
