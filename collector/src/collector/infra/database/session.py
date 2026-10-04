"""Fábrica de sessões SQLAlchemy. Sem create_all."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from collector.infra.database.config import database_url


def create_engine_from_url(url: str | None = None) -> Engine:
    return create_engine(url or database_url(), pool_pre_ping=True)


def create_session_factory(url: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(
        bind=create_engine_from_url(url),
        autoflush=False,
        expire_on_commit=False,
    )
