import asyncio
import base64
import json
import logging

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.repositories.job_repository import JobRepository
from app.services.crawler_service import scrape_url
from app.services.llm_service import extract_job_info
from app.tasks import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="research.parse_jd", soft_time_limit=120)
def task_parse_jd(job_id: str) -> None:
    """Celery task 入口，用 asyncio.run 包异步逻辑，与 FastAPI event loop 解耦"""
    logger.info("task_parse_jd started: job_id=%s", job_id)
    asyncio.run(_do_parse_jd(job_id))


async def _publish_parsed(redis, job_id: str, info) -> None:
    """抽取公共的 parsed 事件发布逻辑"""
    await redis.publish(
        f"job:{job_id}",
        json.dumps({
            "type": "parsed",
            "step": "parse_complete",
            "message": "JD 解析完成，请确认职位信息",
            "title": info.title,
            "company": info.company,
            "requirements": info.requirements,
            "jd_summary": info.jd_summary,
            "salary_range": info.salary_range,
            "location": info.location,
            "work_type": info.work_type,
        }),
    )


async def _do_parse_jd(job_id: str) -> None:
    """
    JD 解析主流程：
    1. 查库拿 url
    2. Firecrawl 抓取（失败 → awaiting_manual_input，等待用户补充内容）
    3. LLM 提取结构化字段
    4. 写回 DB，status → awaiting_confirm
    5. Redis publish parsed 事件
    """
    redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        async with AsyncSessionLocal() as session:
            repo = JobRepository(session)
            job = await repo.get_by_id(job_id)
            if not job:
                return
            job_url = job.url

        logger.info("scraping url: job_id=%s url=%.80s", job_id, job_url)
        # 爬取失败单独处理：引导用户手动输入，而非直接 failed
        try:
            raw_content = await scrape_url(job_url)
            logger.info("scrape ok: job_id=%s content_len=%d", job_id, len(raw_content))
        except Exception:
            logger.warning("JD scrape failed, awaiting manual input: job_id=%s", job_id)
            async with AsyncSessionLocal() as session:
                await JobRepository(session).update_status(job_id, "awaiting_manual_input")
            await redis.publish(
                f"job:{job_id}",
                json.dumps({
                    "type": "awaiting_manual_input",
                    "message": "未能自动提取 JD 内容，请粘贴职位描述或上传截图",
                }),
            )
            return

        logger.info("extracting job info via LLM: job_id=%s", job_id)
        info = await extract_job_info(raw_content)
        logger.info("LLM extraction done: job_id=%s title=%s company=%s", job_id, info.title, info.company)

        async with AsyncSessionLocal() as session:
            repo = JobRepository(session)
            await repo.update_after_parse(
                job_id,
                raw_content=raw_content,
                title=info.title,
                company=info.company,
                requirements=info.requirements,
                jd_summary=info.jd_summary,
                salary_range=info.salary_range,
                location=info.location,
                work_type=info.work_type,
            )

        await _publish_parsed(redis, job_id, info)
    except Exception:
        logger.exception("JD parse task failed: job_id=%s", job_id)
        async with AsyncSessionLocal() as session:
            await JobRepository(session).update_status(job_id, "failed")
        try:
            await redis.publish(
                f"job:{job_id}",
                json.dumps({
                    "type": "error",
                    "job_id": job_id,
                    "code": "UPSTREAM_ERROR",
                    "message": "JD 解析失败，请稍后重试",
                }),
            )
        except Exception:
            logger.exception("Redis publish failed for job error: job_id=%s", job_id)
    finally:
        await redis.aclose()


@celery_app.task(name="research.extract_from_raw", soft_time_limit=120)
def task_extract_from_raw(job_id: str) -> None:
    """从用户粘贴的文本中提取 JD 结构化字段"""
    logger.info("task_extract_from_raw started: job_id=%s", job_id)
    asyncio.run(_do_extract_from_raw(job_id))


async def _do_extract_from_raw(job_id: str) -> None:
    redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        async with AsyncSessionLocal() as session:
            job = await JobRepository(session).get_by_id(job_id)
            if not job or not job.raw_content:
                logger.warning("extract_from_raw: job not found or raw_content empty: job_id=%s", job_id)
                return
            raw_content = job.raw_content

        logger.info("extracting job info from raw text: job_id=%s content_len=%d", job_id, len(raw_content))
        info = await extract_job_info(raw_content)
        logger.info("LLM extraction done: job_id=%s title=%s company=%s", job_id, info.title, info.company)

        async with AsyncSessionLocal() as session:
            await JobRepository(session).update_after_parse(
                job_id,
                raw_content=raw_content,
                title=info.title,
                company=info.company,
                requirements=info.requirements,
                jd_summary=info.jd_summary,
                salary_range=info.salary_range,
                location=info.location,
                work_type=info.work_type,
            )

        await _publish_parsed(redis, job_id, info)
    except Exception:
        logger.exception("Extract from raw failed: job_id=%s", job_id)
        async with AsyncSessionLocal() as session:
            await JobRepository(session).update_status(job_id, "failed")
        try:
            await redis.publish(
                f"job:{job_id}",
                json.dumps({
                    "type": "error",
                    "job_id": job_id,
                    "code": "UPSTREAM_ERROR",
                    "message": "JD 解析失败，请稍后重试",
                }),
            )
        except Exception:
            logger.exception("Redis publish failed: job_id=%s", job_id)
    finally:
        await redis.aclose()


@celery_app.task(name="research.extract_from_images", soft_time_limit=120)
def task_extract_from_images(job_id: str, images_b64: list[str]) -> None:
    """从用户上传的截图中提取 JD 结构化字段"""
    logger.info("task_extract_from_images started: job_id=%s image_count=%d", job_id, len(images_b64))
    asyncio.run(_do_extract_from_images(job_id, images_b64))


async def _do_extract_from_images(job_id: str, images_b64: list[str]) -> None:
    from app.services.llm_service import extract_job_info_from_images

    redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        images_bytes = [base64.b64decode(b64) for b64 in images_b64]
        logger.info("calling GPT-4o Vision: job_id=%s image_count=%d", job_id, len(images_bytes))
        info = await extract_job_info_from_images(images_bytes)
        logger.info("Vision extraction done: job_id=%s title=%s company=%s", job_id, info.title, info.company)

        async with AsyncSessionLocal() as session:
            await JobRepository(session).update_after_parse(
                job_id,
                raw_content="[extracted from images]",
                title=info.title,
                company=info.company,
                requirements=info.requirements,
                jd_summary=info.jd_summary,
                salary_range=info.salary_range,
                location=info.location,
                work_type=info.work_type,
            )

        await _publish_parsed(redis, job_id, info)
    except Exception:
        logger.exception("Extract from images failed: job_id=%s", job_id)
        async with AsyncSessionLocal() as session:
            await JobRepository(session).update_status(job_id, "failed")
        try:
            await redis.publish(
                f"job:{job_id}",
                json.dumps({
                    "type": "error",
                    "job_id": job_id,
                    "code": "UPSTREAM_ERROR",
                    "message": "图片解析失败，请改用文字粘贴",
                }),
            )
        except Exception:
            logger.exception("Redis publish failed: job_id=%s", job_id)
    finally:
        await redis.aclose()


async def _build_initial_state(job_id: str) -> dict | None:
    """从 DB 构建 LangGraph 初始 state，首次运行时调用"""
    async with AsyncSessionLocal() as session:
        repo = JobRepository(session)
        job = await repo.get_by_id(job_id)
        if not job:
            return None

        resume_content = None
        if job.resume_id:
            from app.repositories.resume_repository import ResumeRepository
            resume_repo = ResumeRepository(session)
            resume = await resume_repo.get_by_id(job.resume_id)
            if resume and resume.status == "done":
                parts = []
                if resume.summary:
                    parts.append(resume.summary)
                if resume.skills:
                    parts.append("技能: " + ", ".join(resume.skills))
                if resume.work_experience:
                    exp_lines = []
                    for exp in resume.work_experience:
                        exp_lines.append(
                            (
                                f"{exp.get('company', '')} | "
                                f"{exp.get('title', '')} | "
                                f"{exp.get('duration', '')}"
                            )
                        )
                    if exp_lines:
                        parts.append("工作经历:\n" + "\n".join(exp_lines))
                if resume.education:
                    edu_lines = []
                    for edu in resume.education:
                        edu_lines.append(
                            (
                                f"{edu.get('school', '')} | "
                                f"{edu.get('degree', '')} | "
                                f"{edu.get('major', '')}"
                            )
                        )
                    if edu_lines:
                        parts.append("教育背景:\n" + "\n".join(edu_lines))
                if parts:
                    resume_content = "\n\n".join(parts)

        return {
            "job_id": job_id,
            "url": job.url,
            "title": job.title,
            "company": job.company,
            "requirements": job.requirements or [],
            "selected_directions": job.selected_directions or [],
            "jd_summary": job.jd_summary or "",
            "salary_range": job.salary_range,
            "location": job.location,
            "work_type": job.work_type,
            "resume_content": resume_content,
            "search_results": {},
            "research_analysis": None,
            "draft_sections": None,
            "final_report": None,
            "human_feedback": [],
            "current_step": "search",
            "error": None,
        }


@celery_app.task(name="research.run", soft_time_limit=600)
def task_run_research(job_id: str, resume: bool = False) -> None:
    """LangGraph 研究图入口。

    resume=False 首次运行传 initial_state；resume=True 从 checkpoint 恢复传 None
    """
    asyncio.run(_do_run_research(job_id, resume=resume))


async def _do_run_research(job_id: str, resume: bool = False) -> None:
    from langgraph.errors import GraphInterrupt

    redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        from app.graphs.research_graph import get_research_graph
        graph = get_research_graph()
        config = {"configurable": {"thread_id": job_id}}

        action_data: dict = {}
        if resume:
            raw = await redis.get(f"job:{job_id}:resume_action")
            if raw:
                action_data = json.loads(raw)
                await redis.delete(f"job:{job_id}:resume_action")
                await redis.delete(f"job:{job_id}:pending_interrupt")

            # 检查 checkpoint 是否存在；MemorySaver 在 worker 重启后会丢失
            ckpt = await graph.aget_state(config)
            if not ckpt or not ckpt.next:
                logger.error(
                    "Resume failed: checkpoint not found or already done: job_id=%s", job_id
                )
                async with AsyncSessionLocal() as session:
                    repo = JobRepository(session)
                    await repo.update_status(job_id, "failed")
                await redis.publish(
                    f"job:{job_id}",
                    json.dumps({
                        "type": "error",
                        "job_id": job_id,
                        "code": "CHECKPOINT_LOST",
                        "message": "调研进度丢失（服务重启），请重新提交 Job",
                    }),
                )
                return

            is_edit = action_data.get("action") == "edit"
            if is_edit and action_data.get("edits") and ckpt.values:
                updates = {
                    k: v
                    for k, v in action_data["edits"].items()
                    if k in ckpt.values
                }
                if updates:
                    await graph.aupdate_state(config, updates)

            sv = ckpt.values or {}
            current_step = sv.get("current_step", "")
            existing_fb = sv.get("human_feedback", [])
            await graph.aupdate_state(config, {
                "human_feedback": existing_fb + [{
                    "node": current_step,
                    "action": action_data.get("action", "approve"),
                    "edits": action_data.get("edits"),
                    "feedback": action_data.get("feedback"),
                }],
            })

        if resume:
            from langgraph.types import Command
            # LangGraph 1.x: resume 值不可为 None（会触发 UnboundLocalError）
            input_state = Command(resume=action_data or {"action": "approve"})
        else:
            input_state = await _build_initial_state(job_id)
            if input_state is None:
                return

        try:
            async for event in graph.astream(input_state, config):
                node_name = list(event.keys())[0]
                
                # 转换节点名为友好的中文描述
                friendly_msg = {
                    "search": "正在全球范围内搜索公司背景与技术情报...",
                    "analyze": "正在结合 JD 与您的简历进行深度分析...",
                    "review_results": "搜索分析已完成，等待你确认",
                    "generate_report": "正在起草面试情报报告各章节...",
                    "review_draft": "报告草稿已生成，等待你确认",
                    "finalize": "正在生成最终报告...",
                }.get(node_name, f"正在处理: {node_name}")

                if node_name == "__interrupt__":
                    interrupt_values = event["__interrupt__"]
                    if interrupt_values:
                        val = interrupt_values[0]
                        interrupt_payload = (
                            val.value if hasattr(val, "value") else val
                        )
                        payload_json = json.dumps(interrupt_payload)
                        await redis.setex(
                            f"job:{job_id}:pending_interrupt", 3600, payload_json
                        )
                        await redis.publish(f"job:{job_id}", payload_json)
                else:
                    await redis.publish(
                        f"job:{job_id}",
                        json.dumps({
                            "type": "progress", 
                            "node": node_name,
                            "message": friendly_msg
                        }),
                    )
        except GraphInterrupt as exc:
            for item in (exc.interrupts if hasattr(exc, "interrupts") else []):
                val = item.value if hasattr(item, "value") else item
                payload_json = json.dumps(val)
                await redis.setex(
                    f"job:{job_id}:pending_interrupt", 3600, payload_json
                )
                await redis.publish(f"job:{job_id}", payload_json)
            return

        # stream 正常结束 → 检查是否真正完成（非 interrupt 暂停）
        final_state = await graph.aget_state(config)
        if final_state and not final_state.next:
            fsv = final_state.values or {}
            final_report = fsv.get("final_report")
            if final_report:
                from app.models.report import Report
                report_data = fsv.get("report_data") or {}
                content = json.dumps(report_data, ensure_ascii=False)
                async with AsyncSessionLocal() as session:
                    session.add(Report(
                        job_id=job_id, content=content, status="done",
                    ))
                    repo = JobRepository(session)
                    await repo.update_status(job_id, "done")
                # completed 在 DB 写入后发送，保证前端收到时数据已落库
                await redis.delete(f"job:{job_id}:pending_interrupt")
                await redis.publish(f"job:{job_id}", json.dumps({"type": "completed"}))

    except GraphInterrupt as exc:
        # resume 初始化阶段触发的 interrupt（正常挂起，不是错误）
        for item in (exc.interrupts if hasattr(exc, "interrupts") else []):
            val = item.value if hasattr(item, "value") else item
            payload_json = json.dumps(val)
            await redis.setex(
                f"job:{job_id}:pending_interrupt", 3600, payload_json
            )
            await redis.publish(f"job:{job_id}", payload_json)
    except Exception:
        logger.exception("Research task failed: job_id=%s resume=%s", job_id, resume)
        try:
            await redis.publish(
                f"job:{job_id}",
                json.dumps({
                    "type": "error",
                    "job_id": job_id,
                    "code": "INTERNAL_ERROR",
                    "message": "调研任务异常，请稍后重试",
                }),
            )
        except Exception:
            logger.exception(
                "Redis publish failed for research error: job_id=%s", job_id,
            )
        async with AsyncSessionLocal() as session:
            repo = JobRepository(session)
            await repo.update_status(job_id, "failed")
    finally:
        await redis.aclose()
