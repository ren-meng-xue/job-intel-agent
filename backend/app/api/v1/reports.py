import asyncio
import json

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.repositories.job_repository import JobRepository
from app.schemas.report import ReportResponse
from app.services.auth_service import get_current_user

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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """SSE 端点：订阅 Job 解析进度事件，直到 parsed/error 终态"""
    repo = JobRepository(db)
    job = await repo.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

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
    current_user: User = Depends(get_current_user),
):
    # TODO: Phase 2D — 从 DB 查询报告
    raise NotImplementedError
