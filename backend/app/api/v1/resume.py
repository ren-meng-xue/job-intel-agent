import asyncio
import json

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AppError, ErrorCode
from app.models.resume import Resume
from app.models.user import User
from app.repositories.resume_repository import ResumeRepository
from app.schemas.resume import ResumeDetailResponse, ResumeResponse
from app.services.auth_service import get_current_user
from app.services.resume_service import extract_text
from app.tasks.resume import task_parse_resume

router = APIRouter()

_ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
_MAX_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/", status_code=202, response_model=ResumeResponse)
async def upload_resume(
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传简历（PDF/DOCX），每次上传创建新记录"""
    repo = ResumeRepository(db)

    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise AppError(ErrorCode.BAD_REQUEST, "仅支持 PDF 或 DOCX 格式")

    file_bytes = await file.read()
    if len(file_bytes) > _MAX_SIZE:
        raise AppError(ErrorCode.BAD_REQUEST, "文件超过 10 MB 限制")

    try:
        raw_content = extract_text(file_bytes, file.filename or "")
    except ValueError as e:
        raise AppError(ErrorCode.BAD_REQUEST, str(e))

    resume = Resume(
        user_id=current_user.id,
        filename=file.filename or "resume",
        raw_content=raw_content or None,
        status="parsing",
    )
    resume = await repo.create(resume)
    task_parse_resume.delay(resume.id)
    return resume


@router.get("/", response_model=ResumeDetailResponse)
async def get_resume(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的简历及解析结果"""
    repo = ResumeRepository(db)
    resume = await repo.get_by_user(current_user.id)
    if not resume:
        raise AppError(ErrorCode.NOT_FOUND, "尚未上传简历")
    return resume


@router.get("/{resume_id}/stream")
async def stream_resume(
    resume_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """SSE：订阅简历解析进度，收到 parsed / error 终态事件后关闭"""
    repo = ResumeRepository(db)
    resume = await repo.get_by_id(resume_id)
    if not resume:
        raise AppError(ErrorCode.NOT_FOUND, "简历不存在")
    if resume.user_id != current_user.id:
        raise AppError(ErrorCode.ACCESS_DENIED, "无权访问此简历")

    return StreamingResponse(
        _sse_generator(resume_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete("/{resume_id}", status_code=204)
async def delete_resume(
    resume_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除简历，删除后可重新上传"""
    repo = ResumeRepository(db)
    resume = await repo.get_by_id(resume_id)
    if not resume:
        raise AppError(ErrorCode.NOT_FOUND, "简历不存在")
    if resume.user_id != current_user.id:
        raise AppError(ErrorCode.ACCESS_DENIED, "无权访问此简历")
    await repo.delete(resume_id)


async def _sse_generator(resume_id: str):
    """订阅 Redis resume:{id} 频道，逐条转发 SSE 事件，parsed/error 后主动关闭"""
    redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"resume:{resume_id}")
    try:
        while True:
            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True),
                    timeout=15.0,
                )
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
                continue

            if message is None:
                await asyncio.sleep(0.1)
                continue

            data = message.get("data")
            if not isinstance(data, str):
                continue

            yield f"data: {data}\n\n"

            try:
                if json.loads(data).get("type") in ("parsed", "error"):
                    break
            except (json.JSONDecodeError, AttributeError):
                pass
    finally:
        await pubsub.unsubscribe(f"resume:{resume_id}")
        await pubsub.aclose()
        await redis.aclose()
