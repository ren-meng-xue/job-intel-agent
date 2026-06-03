"""MCP server 工具单元测试 — 验证注册、调用、返回 schema。"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_extract_jd_text_returns_structured():
    """extract_jd_text 工具应调用 extract_job_info 并返回结构化字段。"""
    from app.mcp_server import extract_jd_text
    from app.schemas.job import ExtractedJobInfo

    fake = ExtractedJobInfo(
        title="后端工程师",
        company="字节",
        requirements=["3年经验", "Python"],
        jd_summary="负责核心业务",
        salary_range="25k-50k",
        location="北京",
        work_type="onsite",
    )

    with patch(
        "app.mcp_server._extract_job_info",
        new_callable=AsyncMock,
        return_value=fake,
    ):
        result = await extract_jd_text("某 JD 文本")

    assert result["title"] == "后端工程师"
    assert result["company"] == "字节"
    assert result["requirements"] == ["3年经验", "Python"]
    assert result["work_type"] == "onsite"

@pytest.mark.asyncio
async def test_web_search_returns_results():
    """web_search 透传 Tavily 结果。"""
    from app.mcp_server import web_search

    fake_results = [
        {"title": "字节技术博客", "url": "https://example.com", "content": "摘要"},
    ]

    with patch(
        "app.mcp_server._search",
        new_callable=AsyncMock,
        return_value=fake_results,
    ):
        result = await web_search("字节 后端 技术栈", max_results=3)

    assert result == fake_results

@pytest.mark.asyncio
async def test_analyze_position_returns_summary():
    """analyze_position 调底层 analyze_node，返回 300-500 字分析。"""
    from app.mcp_server import analyze_position

    fake_node_result = {
        "research_analysis": "字节国际化团队近期在做飞书出海，技术栈以 React + Node.js 为主...",
        "current_step": "review_results",
    }

    with patch(
        "app.mcp_server._analyze_node",
        new_callable=AsyncMock,
        return_value=fake_node_result,
    ):
        result = await analyze_position(
            title="国际化前端",
            company="字节",
            jd_summary="负责飞书海外版",
            requirements=["3年 React"],
            search_results={"技术栈": [{"title": "blog", "content": "..."}]},
            resume_content=None,
        )

    assert "国际化团队" in result
    assert isinstance(result, str)

@pytest.mark.asyncio
async def test_generate_position_report_returns_six_modules():
    """generate_position_report 调底层 generate_report_node，返回 6 模块 JSON。"""
    from app.mcp_server import generate_position_report

    fake_node_result = {
        "report_data": {
            "job_interpretation": {"hard_requirements": ["Python"], "soft_requirements": [], "hidden_bonuses": [], "summary": ""},
            "resume_match": {"strengths": ["Python 经验"], "gaps": ["缺分布式"]},
            "company_profile": {"summary": "字节国际化团队", "tags": ["极客", "快节奏"]},
            "interview_qa": [{"question": "Q1", "tip": "T1"}],
            "salary_range": {"market_min": 25000, "market_max": 50000, "median": 35000, "suggested_min": 30000, "suggested_max": 45000},
            "prep_suggestions": [{"title": "3天补分布式", "content": "看 DDIA"}],
        },
        "current_step": "review_draft",
    }

    with patch(
        "app.mcp_server._generate_report_node",
        new_callable=AsyncMock,
        return_value=fake_node_result,
    ):
        result = await generate_position_report(
            title="后端", company="字节",
            jd_summary="...", requirements=["Python"],
            search_results={"技术栈": []},
            directions=["技术栈"],
            resume_content="3 年 Python",
            research_analysis="...",
        )

    assert "job_interpretation" in result
    assert "resume_match" in result
    assert "company_profile" in result
    assert "interview_qa" in result
    assert "salary_range" in result
    assert "prep_suggestions" in result
    assert result["resume_match"]["gaps"] == ["缺分布式"]

@pytest.mark.asyncio
async def test_scrape_jd_url_returns_markdown():
    """scrape_jd_url 透传 Firecrawl 抓取结果。"""
    from app.mcp_server import scrape_jd_url

    with patch(
        "app.mcp_server._scrape_url",
        new_callable=AsyncMock,
        return_value="# 字节 后端工程师\n\n## 职责\n...",
    ):
        result = await scrape_jd_url("https://example.com/job/123")

    assert "字节" in result
    assert "职责" in result


@pytest.mark.asyncio
async def test_extract_resume_returns_structured():
    """extract_resume 透传 LLM 简历解析结果。"""
    from app.mcp_server import extract_resume

    fake = {
        "summary": "3 年 Python 后端",
        "skills": ["Python", "FastAPI"],
        "work_experience": [{"company": "X", "title": "后端", "duration": "2022-2024"}],
        "education": [{"school": "Y", "degree": "本科", "major": "CS"}],
    }

    with patch(
        "app.mcp_server._extract_resume_info",
        new_callable=AsyncMock,
        return_value=fake,
    ):
        result = await extract_resume("简历原文...")

    assert result["summary"] == "3 年 Python 后端"
    assert result["skills"] == ["Python", "FastAPI"]
