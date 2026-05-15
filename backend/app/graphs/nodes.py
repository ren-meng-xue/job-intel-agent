"""LangGraph 研究图各节点实现"""
import json

import redis.asyncio as aioredis

from app.core.config import settings
from app.graphs.state import ResearchState
from app.services.llm_service import chat
from app.services.search_service import search

# 模块级 Redis 单例，内部维护连接池，避免每次 publish 创建新连接
_redis: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


async def _publish_progress(job_id: str, step: str, **extra) -> None:
    await _get_redis().publish(
        f"job:{job_id}",
        json.dumps({"type": "progress", "step": step, **extra}),
    )


async def search_node(state: ResearchState) -> dict:
    """对每个调研方向并行搜索，结果写入 state"""
    if not state["selected_directions"]:
        return {
            "search_results": {},
            "current_step": "analyze",
            "error": "selected_directions 为空，无法执行搜索",
        }

    await _publish_progress(
        state["job_id"], "search",
        directions=state["selected_directions"],
    )

    results = {}
    for direction in state["selected_directions"]:
        query = f"{state['title']} {state['company']} {direction}"
        results[direction] = await search(query)

    return {"search_results": results, "current_step": "analyze"}


def _build_analyze_prompt(state: ResearchState) -> str:
    """构造分析 prompt，包含 JD 信息 + 搜索结果 + 人类反馈历史"""
    prompt = f"""你是一个职位调研分析师，请分析以下搜索结果。

## 职位信息
- 职位：{state['title']}
- 公司：{state['company']}
- JD 摘要：{state['jd_summary']}
- 任职要求：{', '.join(state['requirements'])}

## 搜索结果
"""
    for direction, items in state["search_results"].items():
        prompt += f"\n### {direction}\n"
        for item in items:
            prompt += f"- [{item.get('title', '')}]({item.get('url', '')}): {item.get('content', '')}\n"

    if state["human_feedback"]:
        prompt += "\n## 用户历史反馈\n"
        for fb in state["human_feedback"]:
            prompt += f"- [{fb.get('node', '')}] {fb.get('action', '')}"
            if fb.get("feedback"):
                prompt += f": {fb['feedback']}"
            prompt += "\n"

    prompt += "\n请对以上信息进行综合分析，提炼关键洞察，输出一份中文分析摘要（300-500 字）。"
    return prompt


async def analyze_node(state: ResearchState) -> dict:
    """LLM 综合分析搜索结果，生成 research_analysis"""
    await _publish_progress(state["job_id"], "analyze")

    analysis = await chat(
        messages=[{"role": "user", "content": _build_analyze_prompt(state)}],
        model="gpt-4o",
    )
    return {"research_analysis": analysis, "current_step": "review_results"}


def _build_report_prompt(state: ResearchState) -> str:
    """构造报告生成 prompt"""
    prompt = f"""你是一个职位调研报告撰写人，请基于以下分析生成一份调研报告草稿。

## 职位信息
- 职位：{state['title']}
- 公司：{state['company']}

## 调研分析
{state['research_analysis']}

## 参考来源
"""
    for direction, items in state["search_results"].items():
        prompt += f"\n### {direction}\n"
        for item in items:
            prompt += f"- {item.get('title', '')}: {item.get('url', '')}\n"

    if state["human_feedback"]:
        prompt += "\n## 用户反馈（请据此调整报告）\n"
        for fb in state["human_feedback"]:
            prompt += f"- [{fb.get('node', '')}] {fb.get('action', '')}"
            if fb.get("edits"):
                prompt += f": {fb['edits']}"
            if fb.get("feedback"):
                prompt += f": {fb['feedback']}"
            prompt += "\n"

    prompt += """
请按调研方向分段输出报告草稿，每段包含：关键发现、数据支撑、引用来源。
返回 JSON 格式：{"sections": [{"direction": "方向名", "heading": "标题", "content": "正文", "sources": ["url1", "url2"]}]}
"""
    return prompt


async def generate_report_node(state: ResearchState) -> dict:
    """LLM 基于分析 + 人类反馈生成报告草稿"""
    await _publish_progress(state["job_id"], "generate_report")

    resp = await chat(
        messages=[{"role": "user", "content": _build_report_prompt(state)}],
        model="gpt-4o",
        response_format={"type": "json_object"},
    )
    sections = json.loads(resp).get("sections", [])
    return {"draft_sections": sections, "current_step": "review_draft"}
