"""LangGraph 研究图全局状态定义"""
from typing import TypedDict


class ResearchState(TypedDict):
    """贯穿所有节点的共享状态"""

    # ── 入口信息 ──
    job_id: str
    url: str
    title: str
    company: str
    requirements: list[str]
    selected_directions: list[str]
    jd_summary: str
    salary_range: str | None
    location: str | None
    work_type: str | None

    # ── 研究产出 ──
    search_results: dict[str, list[dict]]
    research_analysis: str | None
    draft_sections: list[dict] | None
    final_report: str | None

    # ── 人类修正（累积）──
    # [{node, action: "approve"|"edit"|"retry", edits, feedback}]
    human_feedback: list[dict]

    # ── 控制 ──
    current_step: str
    error: str | None

    # ── 简历 ──
    resume_content: str | None

    # ── 结构化报告（6 模块 JSON，存入 Report.content）──
    report_data: dict | None
