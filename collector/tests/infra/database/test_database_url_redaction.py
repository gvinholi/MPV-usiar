"""DATABASE_URL nunca aparece com senha em repr, erros de conexão ou logs."""

from __future__ import annotations

import logging

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from collector.infra.database.config import PersistenceConfigError, database_url
from collector.infra.database.session import create_engine_from_url

SENTINEL = "Sentinel-Password-Never-Logged-7f3a"
# Porta 1 em loopback recusa a conexão sem depender de rede externa.
URL = f"postgresql+psycopg://usiar_runtime:{SENTINEL}@127.0.0.1:1/postgres?connect_timeout=2"


def test_missing_database_url_error_has_no_value(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(PersistenceConfigError) as caught:
        database_url()
    assert str(caught.value) == "DATABASE_URL não configurada"


def test_engine_repr_and_connection_errors_hide_password(monkeypatch, caplog):
    monkeypatch.setenv("DATABASE_URL", URL)
    engine = create_engine_from_url()
    caplog.set_level(logging.DEBUG)
    try:
        assert SENTINEL not in repr(engine)
        assert SENTINEL not in str(engine.url)
        with pytest.raises(OperationalError) as caught, engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        assert SENTINEL not in str(caught.value)
        assert SENTINEL not in repr(caught.value)
        assert SENTINEL not in caplog.text
    finally:
        engine.dispose()
