import base64
import json

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AppError, ErrorCode
from app.models.user import User
from app.repositories.job_repository import JobRepository
from app.schemas.job import (
    DirectionsPayload,
    DirectionsResponse,
    JobConfirmPayload,
    JobCreate,
    JobCreateFromText,
    JobDetailResponse,
    JobResponse,
    JobStartPayload,
    RawContentPayload,
    ReparsePayload,
    ResumePayload,
)
from app.services.auth_service import get_current_user
from app.services.llm_service import suggest_directions
from app.tasks.research import (
    task_extract_from_images,
    task_extract_from_raw,
    task_parse_jd,
    task_run_research,
)

router = APIRouter()


@router.post("/", response_model=JobResponse, status_code=201)
async def create_job(
    payload: JobCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建 Job 记录并触发异步解析任务，立即返回 status=parsing"""
    repo = JobRepository(db)
    job = await repo.create_job(
        url=str(payload.url),
        user_id=current_user.id,
        resume_id=payload.resume_id,
    )
    task_parse_jd.delay(job.id)
    return job


@router.get("/{job_id}", response_model=JobDetailResponse)
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 Job 详情"""
    repo = JobRepository(db)
    job = await repo.get_by_id(job_id)
    if not job:
        raise AppError(ErrorCode.NOT_FOUND, "Job 不存在")
    if job.user_id != current_user.id:
        raise AppError(ErrorCode.ACCESS_DENIED, "无权访问此 Job")
    return job


@router.post("/from-text", response_model=JobResponse, status_code=201)
async def create_job_from_text(
    payload: JobCreateFromText,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """用户直接粘贴 JD 文本（无 URL），创建 Job 并触发 LLM 提取"""
    repo = JobRepository(db)
    job = await repo.create_job_from_content(
        raw_content=payload.raw_content,
        user_id=current_user.id,
        resume_id=payload.resume_id,
    )
    task_extract_from_raw.delay(job.id)
    return job


@router.post("/from-images", response_model=JobResponse, status_code=201)
async def create_job_from_images(
    images: list[UploadFile] = File(...),
    resume_id: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """用户上传 JD 截图（最多 3 张），创建 Job 并触发 GPT-4o Vision 提取"""
    if len(images) > 3:
        raise AppError(ErrorCode.VALIDATION_ERROR, "最多上传 3 张截图")
    images_b64 = [
        base64.b64encode(await img.read()).decode()
        for img in images
    ]
    repo = JobRepository(db)
    job = await repo.create_job_from_images(user_id=current_user.id, resume_id=resume_id)
    task_extract_from_images.delay(job.id, images_b64)
    return job


@router.post("/{job_id}/raw-content", response_model=JobResponse)
async def submit_raw_content(
    job_id: str,
    payload: RawContentPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """URL 爬取失败后，用户补充粘贴的 JD 文本，触发 LLM 提取"""
    repo = JobRepository(db)
    job = await repo.get_by_id(job_id)
    if not job:
        raise AppError(ErrorCode.NOT_FOUND, "Job 不存在")
    if job.user_id != current_user.id:
        raise AppError(ErrorCode.ACCESS_DENIED, "无权访问此 Job")
    if job.status not in ("awaiting_manual_input", "parsing"):
        raise AppError(ErrorCode.CONFLICT, f"Job 当前状态为 '{job.status}'，不支持此操作")

    job.raw_content = payload.raw_content
    job.status = "parsing"
    await db.commit()
    await db.refresh(job)
    task_extract_from_raw.delay(job_id)
    return job


@router.post("/{job_id}/confirm", response_model=JobDetailResponse)
async def confirm_job(
    job_id: str,
    payload: JobConfirmPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """用户确认/修正 LLM 提取的 JD 字段，status → awaiting_directions"""
    repo = JobRepository(db)
    job = await repo.get_by_id(job_id)
    if not job:
        raise AppError(ErrorCode.NOT_FOUND, "Job 不存在")
    if job.user_id != current_user.id:
        raise AppError(ErrorCode.ACCESS_DENIED, "无权访问此 Job")
    if job.status != "awaiting_confirm":
        raise AppError(
            ErrorCode.CONFLICT,
            f"Job 当前状态为 '{job.status}'，不支持此操作",
        )

    updated = await repo.confirm_job(
        job_id,
        title=payload.title,
        company=payload.company,
        requirements=payload.requirements,
        jd_summary=payload.jd_summary,
        salary_range=payload.salary_range,
        location=payload.location,
        work_type=payload.work_type,
    )
    # 自动生成首批调研方向建议
    suggestions = await suggest_directions(
        title=updated.title or "",
        company=updated.company or "",
        jd_summary=updated.jd_summary or "",
        requirements=updated.requirements or [],
    )
    result = JobDetailResponse.model_validate(updated)
    result.suggested_directions = suggestions
    return result


@router.post("/{job_id}/start", response_model=JobDetailResponse)
async def start_research(
    job_id: str,
    payload: JobStartPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """用户提交调研方向，status → researching，触发 task_run_research"""
    repo = JobRepository(db)
    job = await repo.get_by_id(job_id)
    if not job:
        raise AppError(ErrorCode.NOT_FOUND, "Job 不存在")
    if job.user_id != current_user.id:
        raise AppError(ErrorCode.ACCESS_DENIED, "无权访问此 Job")
    if job.status != "awaiting_directions":
        raise AppError(
            ErrorCode.CONFLICT,
            f"Job 当前状态为 '{job.status}'，不支持此操作",
        )

    updated = await repo.start_research(job_id, payload.selected_directions)
    task_run_research.delay(job_id)
    return updated


@router.post("/{job_id}/directions", response_model=DirectionsResponse)
async def get_directions(
    job_id: str,
    payload: DirectionsPayload | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """LLM 根据 JD 建议调研方向，用户可通过 feedback 换一批"""
    repo = JobRepository(db)
    job = await repo.get_by_id(job_id)
    if not job:
        raise AppError(ErrorCode.NOT_FOUND, "Job 不存在")
    if job.user_id != current_user.id:
        raise AppError(ErrorCode.ACCESS_DENIED, "无权访问此 Job")

    suggestions = await suggest_directions(
        title=job.title or "",
        company=job.company or "",
        jd_summary=job.jd_summary or "",
        requirements=job.requirements or [],
        feedback=payload.feedback if payload else None,
    )
    return DirectionsResponse(suggestions=suggestions)


@router.post("/{job_id}/reparse", response_model=JobResponse)
async def reparse_job(
    job_id: str,
    payload: ReparsePayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """重新触发 LLM 解析 JD，status 回退到 parsing"""
    repo = JobRepository(db)
    job = await repo.get_by_id(job_id)
    if not job:
        raise AppError(ErrorCode.NOT_FOUND, "Job 不存在")
    if job.user_id != current_user.id:
        raise AppError(ErrorCode.ACCESS_DENIED, "无权访问此 Job")
    if job.status != "awaiting_confirm":
        raise AppError(
            ErrorCode.CONFLICT,
            f"Job 当前状态为 '{job.status}'，不支持此操作",
        )

    await repo.update_status(job_id, "parsing")
    task_parse_jd.delay(job_id)
    await db.refresh(job)
    return job


@router.post("/{job_id}/resume", response_model=JobDetailResponse)
async def resume_job(
    job_id: str,
    payload: ResumePayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """恢复 LangGraph 中断：将用户意图写入 Redis，由 Celery task 在 checkpoint 上应用"""
    if payload.action not in ("approve", "edit", "retry"):
        raise AppError(ErrorCode.VALIDATION_ERROR, "action 须为 approve / edit / retry")

    repo = JobRepository(db)
    job = await repo.get_by_id(job_id)
    if not job:
        raise AppError(ErrorCode.NOT_FOUND, "Job 不存在")
    if job.user_id != current_user.id:
        raise AppError(ErrorCode.ACCESS_DENIED, "无权访问此 Job")
    if job.status != "researching":
        raise AppError(
            ErrorCode.CONFLICT,
            f"Job 当前状态为 '{job.status}'，不支持此操作",
        )

    redis_client = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        await redis_client.setex(
            f"job:{job_id}:resume_action",
            300,
            json.dumps({
                "action": payload.action,
                "edits": payload.edits,
                "feedback": payload.feedback,
            }),
        )
    finally:
        await redis_client.aclose()

    task_run_research.delay(job_id, resume=True)
    return job
