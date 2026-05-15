import asyncio
import json

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.repositories.job_repository import JobRepository
from app.services.crawler_service import scrape_url
from app.services.llm_service import extract_job_info
from app.tasks import celery_app


@celery_app.task(name="research.parse_jd", soft_time_limit=120)
def task_parse_jd(job_id: str) -> None:
    """Celery task 入口，用 asyncio.run 包异步逻辑，与 FastAPI event loop 解耦"""
    asyncio.run(_do_parse_jd(job_id))


async def _do_parse_jd(job_id: str) -> None:
    """
    JD 解析主流程：
    1. 查库拿 url
    2. Firecrawl 抓取
    3. LLM 提取结构化字段
    4. 写回 DB，status → awaiting_confirm
    5. Redis publish parsed 事件
    出错时 status → failed，publish error 事件
    """
    # 每次任务创建新连接，避免跨 event loop 复用旧连接
    redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        async with AsyncSessionLocal() as session:
            repo = JobRepository(session)
            job = await repo.get_by_id(job_id)
            if not job:
                return

            raw_content = await scrape_url(job.url)
            info = await extract_job_info(raw_content)

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

        await redis.publish(
            f"job:{job_id}",
            json.dumps({
                "type": "parsed",
                "title": info.title,
                "company": info.company,
                "requirements": info.requirements,
                "salary_range": info.salary_range,
                "location": info.location,
                "work_type": info.work_type,
            }),
        )
    except Exception:
        async with AsyncSessionLocal() as session:
            repo = JobRepository(session)
            await repo.update_status(job_id, "failed")
        await redis.publish(
            f"job:{job_id}",
            json.dumps({"type": "error", "job_id": job_id}),
        )
    finally:
        await redis.aclose()


async def _build_initial_state(job_id: str) -> dict | None:
    """从 DB 构建 LangGraph 初始 state，首次运行时调用"""
    async with AsyncSessionLocal() as session:
        repo = JobRepository(session)
        job = await repo.get_by_id(job_id)
        if not job:
            return None

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
    """LangGraph 研究图入口。resume=False 首次运行传 initial_state；resume=True 从 checkpoint 恢复传 None"""
    asyncio.run(_do_run_research(job_id, resume=resume))


async def _do_run_research(job_id: str, resume: bool = False) -> None:
    from langgraph.errors import GraphInterrupt

    redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        from app.graphs.research_graph import get_research_graph
        graph = get_research_graph()
        config = {"configurable": {"thread_id": job_id}}

        if resume:
            raw = await redis.get(f"job:{job_id}:resume_action")
            if raw:
                action_data = json.loads(raw)
                await redis.delete(f"job:{job_id}:resume_action")

                state = await graph.aget_state(config)

                if action_data.get("action") == "edit" and action_data.get("edits") and state.values:
                    updates = {k: v for k, v in action_data["edits"].items() if k in state.values}
                    if updates:
                        await graph.aupdate_state(config, updates)

                current_step = state.values.get("current_step", "") if state.values else ""
                existing_fb = state.values.get("human_feedback", []) if state.values else []
                await graph.aupdate_state(config, {
                    "human_feedback": existing_fb + [{
                        "node": current_step,
                        "action": action_data["action"],
                        "edits": action_data.get("edits"),
                        "feedback": action_data.get("feedback"),
                    }],
                })

        input_state = None if resume else await _build_initial_state(job_id)
        if input_state is None and not resume:
            return

        try:
            async for event in graph.astream(input_state, config):
                node_name = list(event.keys())[0]
                if node_name == "__interrupt__":
                    interrupt_values = event["__interrupt__"]
                    if interrupt_values:
                        val = interrupt_values[0]
                        interrupt_payload = val.value if hasattr(val, "value") else val
                        await redis.publish(f"job:{job_id}", json.dumps(interrupt_payload))
                else:
                    await redis.publish(
                        f"job:{job_id}",
                        json.dumps({"type": "progress", "node": node_name}),
                    )
        except GraphInterrupt as exc:
            for item in (exc.interrupts if hasattr(exc, "interrupts") else []):
                val = item.value if hasattr(item, "value") else item
                await redis.publish(f"job:{job_id}", json.dumps(val))
            return

        # stream 正常结束 → 检查是否真正完成（非 interrupt 暂停）
        final_state = await graph.aget_state(config)
        if final_state and not final_state.next:
            final_report = final_state.values.get("final_report") if final_state.values else None
            if final_report:
                from app.models.report import Report
                async with AsyncSessionLocal() as session:
                    session.add(Report(job_id=job_id, content=final_report, status="done"))
                    repo = JobRepository(session)
                    await repo.update_status(job_id, "done")
                # completed 在 DB 写入后发送，保证前端收到时数据已落库
                await redis.publish(f"job:{job_id}", json.dumps({"type": "completed"}))

    except GraphInterrupt as exc:
        # resume 初始化阶段触发的 interrupt（正常挂起，不是错误）
        for item in (exc.interrupts if hasattr(exc, "interrupts") else []):
            val = item.value if hasattr(item, "value") else item
            await redis.publish(f"job:{job_id}", json.dumps(val))
    except Exception:
        await redis.publish(
            f"job:{job_id}",
            json.dumps({"type": "error", "job_id": job_id}),
        )
        async with AsyncSessionLocal() as session:
            repo = JobRepository(session)
            await repo.update_status(job_id, "failed")
    finally:
        await redis.aclose()
