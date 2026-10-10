"""Internal authentication domain and application services."""

from .bootstrap import BootstrapAdmin, BootstrapAlreadyCompletedError
from .models import (
    ADMIN_PERMISSIONS,
    AuditEvent,
    AuditOutcome,
    AuthenticatedInternalSession,
    InternalPermission,
    InternalSession,
    InternalUser,
    LoginAttempt,
    LoginAttemptReservation,
    SessionRevocationResult,
    normalize_email,
)
from .passwords import PasswordHasher, PasswordPolicyError
from .ports import InternalAuthRepository
from .rate_limit import LoginRatePolicy, RateLimitKeyDeriver
from .services import (
    AuthenticationCapacityError,
    AuthenticationRateLimitedError,
    CreatedSession,
    InternalLoginService,
    InternalSessionService,
    InvalidCredentialsError,
    InvalidCsrfTokenError,
    InvalidInternalSessionError,
)
from .tokens import generate_session_secrets, parse_csrf_token, parse_session_token

__all__ = [
    "ADMIN_PERMISSIONS",
    "AuditEvent",
    "AuditOutcome",
    "AuthenticatedInternalSession",
    "AuthenticationCapacityError",
    "AuthenticationRateLimitedError",
    "BootstrapAdmin",
    "BootstrapAlreadyCompletedError",
    "CreatedSession",
    "InternalAuthRepository",
    "InternalLoginService",
    "InternalPermission",
    "InternalSession",
    "InternalSessionService",
    "InternalUser",
    "InvalidCredentialsError",
    "InvalidCsrfTokenError",
    "InvalidInternalSessionError",
    "LoginAttempt",
    "LoginAttemptReservation",
    "LoginRatePolicy",
    "PasswordHasher",
    "PasswordPolicyError",
    "RateLimitKeyDeriver",
    "SessionRevocationResult",
    "generate_session_secrets",
    "normalize_email",
    "parse_csrf_token",
    "parse_session_token",
]
