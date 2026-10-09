"""Internal authentication foundation; no HTTP authentication is exposed yet."""

from .bootstrap import BootstrapAdmin, BootstrapAlreadyCompletedError
from .models import (
    ADMIN_PERMISSIONS,
    AuditEvent,
    AuditOutcome,
    InternalPermission,
    InternalSession,
    InternalUser,
    LoginAttempt,
    normalize_email,
)
from .passwords import PasswordHasher, PasswordPolicyError
from .ports import InternalAuthRepository

__all__ = [
    "ADMIN_PERMISSIONS",
    "AuditEvent",
    "AuditOutcome",
    "BootstrapAdmin",
    "BootstrapAlreadyCompletedError",
    "InternalAuthRepository",
    "InternalPermission",
    "InternalSession",
    "InternalUser",
    "LoginAttempt",
    "PasswordHasher",
    "PasswordPolicyError",
    "normalize_email",
]
