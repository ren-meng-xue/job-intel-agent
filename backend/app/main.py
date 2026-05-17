import logging

import redis.asyncio as aioredis
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.database import engine
from app.core.errors import AppError, ErrorCode
from app.schemas.common import ErrorResponse

logger = logging.getLogger(__name__)

app = FastAPI(title="Job Intel Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"https://[a-zA-Z0-9-]+-ren-meng-xues-projects\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router, prefix="/api/v1")


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning(
        "AppError: %s %s — %s: %s",
        request.method, request.url, exc.code.value, exc.message,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            code=exc.code.value,
            message=exc.message,
            detail=exc.detail or None,
        ).model_dump(),
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request, exc: StarletteHTTPException,
) -> JSONResponse:
    code_map: dict[int, ErrorCode] = {
        400: ErrorCode.BAD_REQUEST,
        401: ErrorCode.AUTH_TOKEN_INVALID,
        403: ErrorCode.ACCESS_DENIED,
        404: ErrorCode.NOT_FOUND,
        409: ErrorCode.CONFLICT,
        422: ErrorCode.VALIDATION_ERROR,
        429: ErrorCode.RATE_LIMITED,
    }
    code = code_map.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            code=code.value,
            message=str(exc.detail),
        ).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            code=ErrorCode.VALIDATION_ERROR.value,
            message="请求参数校验失败",
            detail={"errors": exc.errors()},
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception: %s %s", request.method, request.url)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            code=ErrorCode.INTERNAL_ERROR.value,
            message="服务器内部错误",
        ).model_dump(),
    )


@app.get("/health")
async def health():
    checks: dict[str, str] = {}

    # DB
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as exc:
        checks["db"] = f"error: {exc}"
        logger.warning("Health check DB failed: %s", exc)

    # Redis / Celery broker
    try:
        r = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            await r.ping()
            checks["redis"] = "ok"
        finally:
            await r.aclose()
    except Exception as exc:
        checks["redis"] = f"error: {exc}"
        logger.warning("Health check Redis failed: %s", exc)

    all_ok = all(v == "ok" for v in checks.values())
    return {
        "status": "ok" if all_ok else "degraded",
        "checks": checks,
    }


# catch-all：匹配未注册的 /api/v1/* 路径，返回结构化 404
@app.api_route(
    "/api/v1/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def api_not_found(request: Request, path: str):
    return JSONResponse(
        status_code=404,
        content=ErrorResponse(
            code=ErrorCode.NOT_FOUND.value,
            message=f"接口不存在: /api/v1/{path}",
        ).model_dump(),
    )
