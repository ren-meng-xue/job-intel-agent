import asyncio
import json
import logging

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.repositories.resume_repository import ResumeRepository
from app.services.llm_service import extract_resume_info
from app.tasks import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="resume.parse", soft_time_limit=120)
def task_parse_resume(resume_id: str) -> None:
    """Celery task 入口，用 asyncio.run 包异步逻辑，与 FastAPI event loop 解耦"""
    asyncio.run(_do_parse_resume(resume_id))


async def _do_parse_resume(resume_id: str) -> None:
    """
    简历解析主流程：
    1. 查库拿 raw_content
    2. 检查文本是否为空（扫描版 PDF）
    3. LLM 提取结构化字段
    4. 写回 DB，status → done
    5. Redis publish parsed 事件
    出错时 status → failed，publish error 事件
    """
    redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    channel = f"resume:{resume_id}"
    try:
        async with AsyncSessionLocal() as session:
            repo = ResumeRepository(session)
            resume = await repo.get_by_id(resume_id)
            if not resume:
                return

        if not resume.raw_content:
            async with AsyncSessionLocal() as session:
                repo = ResumeRepository(session)
                await repo.update_status(
                    resume_id,
                    "failed",
                    error="文件文本为空，可能是扫描版 PDF，暂不支持",
                )
            error_msg = json.dumps({"type": "error", "resume_id": resume_id})
            await redis.publish(channel, error_msg)
            return

        info = await extract_resume_info(resume.raw_content)

        async with AsyncSessionLocal() as session:
            repo = ResumeRepository(session)
            await repo.update_after_parse(
                resume_id,
                skills=info.get("skills"),
                experience_years=info.get("experience_years"),
                work_experience=info.get("work_experience"),
                education=info.get("education"),
                summary=info.get("summary"),
            )

        parsed_msg = json.dumps({"type": "parsed", "resume_id": resume_id})
        await redis.publish(channel, parsed_msg)

    except Exception as e:
        logger.exception("Resume parse task failed: resume_id=%s", resume_id)
        async with AsyncSessionLocal() as session:
            repo = ResumeRepository(session)
            await repo.update_status(resume_id, "failed", error=str(e))
        try:
            error_msg = json.dumps({"type": "error", "resume_id": resume_id})
            await redis.publish(channel, error_msg)
        except Exception:
            logger.exception(
                "Redis publish failed for resume error: resume_id=%s",
                resume_id,
            )
    finally:
        await redis.aclose()
