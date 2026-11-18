from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# Shared error codes. Mirrored in shared/api-contracts/error_codes.json and both mobile clients.
STATUS_BY_CODE: dict[str, int] = {
    "AUTH_REQUIRED": 401,
    "AUTH_INVALID": 401,
    "FORBIDDEN": 403,
    "NOT_FOUND": 404,
    "VALIDATION_FAILED": 422,
    "RECIPE_INVALID": 422,
    "MIX_INVALID": 422,
    "STORYBOARD_INVALID": 422,
    "MODERATION_BLOCKED": 422,
    "UPLOAD_REJECTED": 422,
    "RATE_LIMITED": 429,
    "QUOTA_EXCEEDED": 429,
    "IDEMPOTENCY_CONFLICT": 409,
    "RENDER_NOT_CANCELLABLE": 409,
    "RENDER_NOT_RETRYABLE": 409,
    "RENDER_NOT_READY": 409,
    "SIGNATURE_INVALID": 403,
    "SIGNATURE_EXPIRED": 403,
    "INTERNAL": 500,
}
RETRYABLE = {"RATE_LIMITED", "INTERNAL"}


class AppError(Exception):
    def __init__(self, code: str, message: str, details: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or []

    @property
    def status_code(self) -> int:
        return STATUS_BY_CODE.get(self.code, 400)


def error_body(code: str, message: str, details: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or [], "retryable": code in RETRYABLE}}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=error_body(exc.code, exc.message, exc.details))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"code": "FIELD_INVALID", "field": ".".join(str(p) for p in e.get("loc", [])), "message": e.get("msg", "")}
            for e in exc.errors()
        ]
        return JSONResponse(status_code=422, content=error_body("VALIDATION_FAILED", "Request is invalid", details))
