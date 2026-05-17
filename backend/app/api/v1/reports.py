import asyncio
import json

import redis.asyncio as aioredis
import redis.exceptions
from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AppError, ErrorCode
from app.models.report import Report
from app.models.user import User
from app.repositories.job_repository import JobRepository
from app.schemas.report import ReportData, ReportResponse
from app.services.auth_service import get_current_user, get_user_by_raw_token

router = APIRouter()


async def _sse_generator(job_id: str):
    """
    订阅 Redis Pub/Sub channel job:{job_id}，将消息以 SSE 格式逐条 yield。
    客户端断连时（GeneratorExit），在 finally 块中清理订阅和 Redis 连接。
    每 15 秒发送一次 keep-alive 注释行，防止代理超时断连。
    """
    redis: aioredis.Redis = await aioredis.from_url(
        settings.REDIS_URL, decode_responses=True
    )
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"job:{job_id}")

    try:
        # 回放：检查 pending interrupt（刷新/重连场景恢复）
        pending = await redis.get(f"job:{job_id}:pending_interrupt")
        if pending:
            yield f"data: {pending}\n\n"

        while True:
            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True),
                    timeout=15.0,
                )
            except asyncio.TimeoutError:
                # 15 秒无消息，发 keep-alive 防止代理断连
                yield ": keep-alive\n\n"
                continue
            except redis.exceptions.ConnectionError:
                yield f"data: {json.dumps({'type': 'error', 'message': '服务暂时不可用，请刷新重试'})}\n\n"
                break

            if message is None:
                await asyncio.sleep(0.1)
                continue

            data = message.get("data")
            if not isinstance(data, str):
                continue

            yield f"data: {data}\n\n"

            # parsed / error 是终态事件，主动关闭流
            try:
                payload = json.loads(data)
                if payload.get("type") in ("parsed", "error"):
                    break
            except (json.JSONDecodeError, AttributeError):
                pass

    finally:
        await pubsub.unsubscribe(f"job:{job_id}")
        await pubsub.aclose()
        await redis.aclose()


@router.get("/{job_id}/stream")
async def stream_report(
    job_id: str,
    token: str | None = Query(None),
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """SSE 端点：订阅 Job 解析进度事件，直到 parsed/error 终态。

    EventSource 不支持自定义 header，故同时接受 ?token= query param。
    优先级：Authorization header > ?token query param。
    """
    raw_token: str | None = None
    if authorization and authorization.startswith("Bearer "):
        raw_token = authorization[7:]
    elif token:
        raw_token = token

    if not raw_token:
        raise AppError(ErrorCode.AUTH_TOKEN_MISSING, "未提供认证 token")

    current_user = await get_user_by_raw_token(raw_token, db)

    repo = JobRepository(db)
    job = await repo.get_by_id(job_id)
    if not job:
        raise AppError(ErrorCode.NOT_FOUND, "Job 不存在")
    if job.user_id != current_user.id:
        raise AppError(ErrorCode.ACCESS_DENIED, "无权访问此 Job")

    return StreamingResponse(
        _sse_generator(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import select
    report = await db.get(Report, report_id)
    # 前端 URL 使用 job_id，兼容通过 job_id 查找
    if not report:
        stmt = select(Report).where(Report.job_id == report_id).limit(1)
        result = await db.execute(stmt)
        report = result.scalar_one_or_none()
    if not report:
        raise AppError(ErrorCode.NOT_FOUND, "Report 不存在")

    repo = JobRepository(db)
    job = await repo.get_by_id(report.job_id)
    if not job:
        raise AppError(ErrorCode.NOT_FOUND, "Job 不存在")
    if job.user_id != current_user.id:
        raise AppError(ErrorCode.ACCESS_DENIED, "无权访问此 Report")

    data = None
    if report.content:
        try:
            raw = json.loads(report.content)
            data = ReportData(**raw)
        except Exception:
            data = None

    return ReportResponse(
        id=report.id,
        job_id=report.job_id,
        status=report.status,
        data=data,
    )
