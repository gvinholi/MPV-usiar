"""Internal login and logout endpoints."""

from typing import Annotated

from fastapi import APIRouter, Header, Request, Security
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from collector.application.internal_auth import (
    AuthenticationCapacityError,
    AuthenticationRateLimitedError,
    InternalLoginService,
    InternalSessionService,
    InvalidCredentialsError,
    InvalidCsrfTokenError,
    InvalidInternalSessionError,
    PasswordPolicyError,
)

from .auth_schemas import InternalLoginRequest, InternalSessionResponse
from .schemas import ErrorResponse
from .security import AuthenticationError, AuthenticationUnavailableError


class InternalAuthInputError(Exception):
    pass


class InternalAuthRateLimitError(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds


def internal_auth_router(
    login_service: InternalLoginService,
    session_service: InternalSessionService,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
    bearer = HTTPBearer(auto_error=False, bearerFormat="opaque")
    errors = {
        status: {"model": ErrorResponse}
        for status in (401, 403, 413, 422, 429, 500, 503)
    }

    @router.post(
        "/session",
        status_code=201,
        response_model=InternalSessionResponse,
        responses=errors,
    )
    def create_session(
        payload: InternalLoginRequest,
        request: Request,
    ) -> JSONResponse:
        try:
            created = login_service.login(
                payload.email,
                payload.password,
                request_id=request.state.request_id,
            )
        except (ValueError, PasswordPolicyError) as exc:
            raise InternalAuthInputError from exc
        except InvalidCredentialsError as exc:
            raise AuthenticationError("invalid credentials") from exc
        except AuthenticationRateLimitedError as exc:
            raise InternalAuthRateLimitError(exc.retry_after_seconds) from exc
        except AuthenticationCapacityError as exc:
            raise AuthenticationUnavailableError(
                "password verification capacity unavailable"
            ) from exc
        except Exception as exc:
            raise AuthenticationUnavailableError(
                "internal authentication store unavailable"
            ) from exc
        body = InternalSessionResponse(
            token_type="Bearer",
            session_token=created.session_token,
            csrf_token=created.csrf_token,
            idle_expires_at=created.idle_expires_at,
            absolute_expires_at=created.absolute_expires_at,
        )
        return JSONResponse(
            status_code=201,
            content=body.model_dump(mode="json"),
            headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
        )

    @router.delete("/session", status_code=204, responses=errors)
    def delete_session(
        request: Request,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer)],
        csrf_token: Annotated[
            str | None, Header(alias="X-CSRF-Token", max_length=128)
        ] = None,
    ) -> Response:
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise AuthenticationError("bearer credential required")
        if csrf_token is None:
            raise InvalidCsrfTokenError
        try:
            session_service.logout(
                credentials.credentials,
                csrf_token,
                request_id=request.state.request_id,
            )
        except InvalidCsrfTokenError:
            raise
        except InvalidInternalSessionError as exc:
            raise AuthenticationError("invalid bearer token") from exc
        except Exception as exc:
            raise AuthenticationUnavailableError(
                "internal authentication store unavailable"
            ) from exc
        return Response(
            status_code=204,
            headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
        )

    return router
