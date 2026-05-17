"""LangGraph 研究图各节点实现"""
import json

from app.graphs.state import ResearchState
from app.services.llm_service import chat
from app.services.search_service import search

async def search_node(state: ResearchState) -> dict:
    """对每个调研方向并行搜索，结果写入 state"""
    if not state["selected_directions"]:
        return {
            "search_results": {},
            "current_step": "analyze",
            "error": "selected_directions 为空，无法执行搜索",
        }

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
    analysis = await chat(
        messages=[{"role": "user", "content": _build_analyze_prompt(state)}],
        model="gpt-4o-mini",
    )
    return {"research_analysis": analysis, "current_step": "review_results"}


def _build_report_prompt(state: ResearchState) -> str:
    """构造结构化 6 模块报告生成 prompt"""
    has_resume = bool(state.get("resume_content"))
    resume_section = f"\n## 候选人简历摘要\n{state.get('resume_content', '')}\n" if has_resume else ""
    salary_hint = f"JD 中标注薪资：{state['salary_range']}" if state.get("salary_range") else "JD 未标注薪资，请基于市场调研估算"

    search_summary = ""
    for direction, items in state.get("search_results", {}).items():
        search_summary += f"\n### {direction}\n"
        for item in (items or [])[:3]:
            search_summary += f"- {item.get('title', '')}: {item.get('snippet', item.get('url', ''))}\n"

    strengths_hint = "基于简历内容分析" if has_resume else "基于行业通用标准给出示例"

    return f"""你是一位专业的求职情报分析师。请基于以下信息，生成一份结构化面试情报报告。

## 职位信息
- 职位：{state['title']}
- 公司：{state['company']}
- 核心要求：{', '.join(state.get('requirements', []))}
- JD 摘要：{state.get('jd_summary', '')}
- {salary_hint}
{resume_section}
## 调研分析
{state.get('research_analysis', '')}

## 调研来源数据
{search_summary}

## 输出要求
返回严格的 JSON，包含以下 6 个模块：

{{
  "job_interpretation": {{
    "hard_requirements": ["硬性要求标签列表，3-6个"],
    "soft_requirements": ["软性偏好标签列表，2-4个"],
    "hidden_bonuses": ["隐性加分项列表，1-3个"],
    "summary": "对该岗位的 AI 解读，2-3句话，揭示隐性门槛和真实要求"
  }},
  "resume_match": {{
    "strengths": ["优势匹配点列表，每条15字内，{strengths_hint}"],
    "gaps": ["待补强 Gap 列表，每条15字内"]
  }},
  "company_profile": {{
    "summary": "公司近期动态和团队画像，3-4句话",
    "tags": ["画像标签，3-5个，如：规模扩张期/技术中台化/晋升节奏快"]
  }},
  "interview_qa": [
    {{
      "question": "高概率面试题，结合JD和候选人背景",
      "tip": "答题思路，50字内，聚焦具体方法论"
    }}
  ],
  "salary_range": {{
    "market_min": 最低市场薪资整数月薪元,
    "market_max": 最高市场薪资整数月薪元,
    "median": 市场中位数整数月薪元,
    "suggested_min": 建议报价下限整数月薪元,
    "suggested_max": 建议报价上限整数月薪元
  }},
  "prep_suggestions": [
    {{
      "title": "建议标题含时间预期如3天",
      "content": "具体行动方案40字内"
    }}
  ]
}}

要求：
- interview_qa 给出 3-5 道题
- prep_suggestions 给出 3-4 条，优先针对 Gap
- salary_range 单位统一为月薪（元），若无法估算则填 0
- 所有字段不可为 null，列表最少 1 个元素
"""


async def generate_report_node(state: ResearchState) -> dict:
    """LLM 生成结构化 6 模块报告"""
    resp = await chat(
        messages=[{"role": "user", "content": _build_report_prompt(state)}],
        model="gpt-4o",
        response_format={"type": "json_object"},
    )
    try:
        report_data = json.loads(resp)
    except (json.JSONDecodeError, TypeError):
        report_data = {}

    # 构造 draft_sections 供 review_draft 中断展示
    draft_sections = []
    ji = report_data.get("job_interpretation", {})
    if ji:
        draft_sections.append({
            "heading": "职位解读",
            "content": (
                f"**硬性要求：** {', '.join(ji.get('hard_requirements', []))}\n\n"
                f"**软性偏好：** {', '.join(ji.get('soft_requirements', []))}\n\n"
                f"**隐性加分项：** {', '.join(ji.get('hidden_bonuses', []))}\n\n"
                f"{ji.get('summary', '')}"
            ),
        })
    rm = report_data.get("resume_match", {})
    if rm:
        draft_sections.append({
            "heading": "简历匹配度",
            "content": (
                f"**优势匹配：** {', '.join(rm.get('strengths', []))}\n\n"
                f"**待补强 Gap：** {', '.join(rm.get('gaps', []))}"
            ),
        })
    cp = report_data.get("company_profile", {})
    if cp:
        draft_sections.append({
            "heading": "公司画像",
            "content": (
                f"{cp.get('summary', '')}\n\n"
                f"**标签：** {', '.join(cp.get('tags', []))}"
            ),
        })
    iqa = report_data.get("interview_qa", [])
    if iqa:
        draft_sections.append({
            "heading": "面试题预测",
            "content": "\n\n".join([
                f"**Q{i+1}：** {qa.get('question', '')}\n\n**答题思路：** {qa.get('tip', '')}"
                for i, qa in enumerate(iqa)
            ]),
        })
    sr = report_data.get("salary_range", {})
    if sr:
        draft_sections.append({
            "heading": "薪资参考",
            "content": (
                f"市场最低：{sr.get('market_min', 0):,} 元/月\n"
                f"市场中位数：{sr.get('median', 0):,} 元/月\n"
                f"市场最高：{sr.get('market_max', 0):,} 元/月\n"
                f"建议报价：{sr.get('suggested_min', 0):,} - {sr.get('suggested_max', 0):,} 元/月"
            ),
        })
    ps = report_data.get("prep_suggestions", [])
    if ps:
        draft_sections.append({
            "heading": "备战建议",
            "content": "\n\n".join([
                f"**{i+1}. {s.get('title', '')}**\n{s.get('content', '')}"
                for i, s in enumerate(ps)
            ]),
        })

    return {
        "report_data": report_data,
        "draft_sections": draft_sections,
        "final_report": json.dumps(report_data, ensure_ascii=False),
        "current_step": "review_draft",
    }
