"""Retry configurável. A espera é injetável para os testes não dormirem."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import sleep

from collector.application.publications.errors import TransientFetchError

Waiter = Callable[[float], None]


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_delay_seconds: float = 0.5
    backoff_factor: float = 2.0
    max_delay_seconds: float = 8.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts deve ser >= 1")
        if self.initial_delay_seconds < 0 or self.max_delay_seconds < 0:
            raise ValueError("atrasos não podem ser negativos")
        if self.backoff_factor < 1:
            raise ValueError("backoff_factor deve ser >= 1")


def default_waiter(seconds: float) -> None:
    sleep(seconds)


def retry_call(operation: Callable[[], object], policy: RetryPolicy, waiter: Waiter) -> object:
    delay = policy.initial_delay_seconds
    last_error: TransientFetchError | None = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return operation()
        except TransientFetchError as exc:
            last_error = exc
            if attempt >= policy.max_attempts:
                raise
            waiter(delay)
            delay = min(delay * policy.backoff_factor, policy.max_delay_seconds)
    raise last_error  # pragma: no cover
