"""Job-Intel MCP Server — 让外部 Agent 系统能调用本项目的能力。

V1 暴露 4 必选 + 2 可选工具，复用现有 service 函数，无状态、不写 DB。
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    name="job-intel",
    host=os.getenv("MCP_HOST", "::"),       # IPv6，兼容 Railway 私网
    port=int(os.getenv("PORT", "9001")),
)

from app.services.llm_service import extract_job_info as _extract_job_info


@mcp.tool()
async def extract_jd_text(text: str) -> dict:
    """把 JD 文本变结构化字段。输入：JD 原文；输出：title / company / requirements / jd_summary / salary_range / location / work_type。"""
    info = await _extract_job_info(text)
    return {
        "title": info.title,
        "company": info.company,
        "requirements": info.requirements,
        "jd_summary": info.jd_summary,
        "salary_range": info.salary_range,
        "location": info.location,
        "work_type": info.work_type,
    }


from app.services.search_service import search as _search


@mcp.tool()
async def web_search(query: str, max_results: int = 5) -> list[dict]:
    """联网搜索目标公司/岗位背景。返回 [{title, url, content}] 列表。"""
    return await _search(query, max_results=max_results)


from app.graphs.nodes import analyze_node as _analyze_node


@mcp.tool()
async def analyze_position(
    title: str,
    company: str,
    jd_summary: str,
    requirements: list[str],
    search_results: dict,
    resume_content: str | None = None,
) -> str:
    """综合 JD + 搜索结果 + 简历，产出 300-500 字分析摘要。"""
    state = {
        "title": title,
        "company": company,
        "jd_summary": jd_summary,
        "requirements": requirements,
        "search_results": search_results,
        "resume_content": resume_content,
        "human_feedback": [],
    }
    result = await _analyze_node(state)
    return result["research_analysis"]


from app.graphs.nodes import generate_report_node as _generate_report_node


@mcp.tool()
async def generate_position_report(
    title: str,
    company: str,
    jd_summary: str,
    requirements: list[str],
    search_results: dict,
    directions: list[str],
    resume_content: str | None = None,
    research_analysis: str | None = None,
    salary_range: str | None = None,
    location: str | None = None,
    work_type: str | None = None,
) -> dict:
    """综合所有素材，产出 6 模块结构化情报报告。"""
    state = {
        "title": title,
        "company": company,
        "jd_summary": jd_summary,
        "requirements": requirements,
        "search_results": search_results,
        "selected_directions": directions,
        "resume_content": resume_content,
        "research_analysis": research_analysis or "",
        "salary_range": salary_range,
        "location": location,
        "work_type": work_type,
        "human_feedback": [],
    }
    result = await _generate_report_node(state)
    return result.get("report_data") or {}


from app.services.crawler_service import scrape_url as _scrape_url
from app.services.llm_service import extract_resume_info as _extract_resume_info


@mcp.tool()
async def scrape_jd_url(url: str) -> str:
    """抓取 JD 网页正文 markdown。Firecrawl 失败会抛错。"""
    return await _scrape_url(url)


@mcp.tool()
async def extract_resume(raw_content: str) -> dict:
    """简历原文结构化。返回 {summary, skills[], work_experience[], education[]}。"""
    return await _extract_resume_info(raw_content)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
