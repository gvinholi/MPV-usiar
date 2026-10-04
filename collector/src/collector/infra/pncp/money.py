"""Conversão segura de valores monetários do PNCP para Decimal."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from math import isfinite

from collector.infra.pncp.errors import PncpInvalidMoneyError, PncpInvalidTypeError


def parse_pncp_money(value: object, *, field: str) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise PncpInvalidTypeError(f"{field} não pode ser booleano", field=field)
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return Decimal(text)
        except InvalidOperation as exc:
            raise PncpInvalidMoneyError(f"{field} não é um valor monetário válido", field=field) from exc
    if isinstance(value, float):
        if not isfinite(value):
            raise PncpInvalidMoneyError(f"{field} não é um valor monetário finito", field=field)
        return Decimal(str(value))
    raise PncpInvalidTypeError(f"{field} tem tipo inválido para valor monetário", field=field)
