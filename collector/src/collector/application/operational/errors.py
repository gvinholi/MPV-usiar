"""Operational runner errors safe for CLI decisions."""


class OperationalRunAlreadyRunningError(RuntimeError):
    """Another process owns the shared collection lock."""
