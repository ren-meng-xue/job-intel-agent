"""统一错误码体系。所有 API / Service 层通过 AppError 抛出结构化错误。"""

from enum import Enum


class ErrorCode(str, Enum):
    """业务错误码，前端据此做分支处理"""
    # ---- 认证 ----
    AUTH_TOKEN_MISSING = "AUTH_TOKEN_MISSING"
    AUTH_TOKEN_INVALID = "AUTH_TOKEN_INVALID"
    AUTH_TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED"
    AUTH_REFRESH_INVALID = "AUTH_REFRESH_INVALID"
    AUTH_CREDENTIALS_WRONG = "AUTH_CREDENTIALS_WRONG"

    # ---- 资源 ----
    NOT_FOUND = "NOT_FOUND"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    ACCESS_DENIED = "ACCESS_DENIED"

    # ---- 业务 ----
    CONFLICT = "CONFLICT"
    BAD_REQUEST = "BAD_REQUEST"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    RATE_LIMITED = "RATE_LIMITED"

    # ---- 服务端 ----
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UPSTREAM_ERROR = "UPSTREAM_ERROR"


# ErrorCode → HTTP status code 映射
_ERROR_CODE_STATUS: dict[ErrorCode, int] = {
    ErrorCode.AUTH_TOKEN_MISSING: 401,
    ErrorCode.AUTH_TOKEN_INVALID: 401,
    ErrorCode.AUTH_TOKEN_EXPIRED: 401,
    ErrorCode.AUTH_REFRESH_INVALID: 401,
    ErrorCode.AUTH_CREDENTIALS_WRONG: 401,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.ALREADY_EXISTS: 409,
    ErrorCode.ACCESS_DENIED: 403,
    ErrorCode.CONFLICT: 409,
    ErrorCode.BAD_REQUEST: 400,
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.UPSTREAM_ERROR: 502,
}


class AppError(Exception):
    """携带 ErrorCode 的异常，由 FastAPI exception handler 统一转换为 ErrorResponse"""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        detail: dict | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.detail = detail or {}
        self.status_code = _ERROR_CODE_STATUS.get(code, 500)
        super().__init__(message)
