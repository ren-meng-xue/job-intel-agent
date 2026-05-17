"""
最小 demo：逐步验证本地 .env 配置
1. OpenAI API 连通性
2. Tavily 搜索 API
3. LangGraph 最小图（无 LLM）
4. 真实 research 图 search 节点（Tavily + LangGraph）
"""
import asyncio
import os
import sys
from pathlib import Path

# 让脚本能 import backend/app 模块
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


def ok(msg): print(f"\033[32m✅  {msg}\033[0m")
def fail(msg): print(f"\033[31m❌  {msg}\033[0m")
def info(msg): print(f"\033[34m→   {msg}\033[0m")
def section(msg):
    print(f"\n\033[1m── {msg} {'─'*(50-len(msg))}\033[0m")


# ─── Step 1: 环境变量检查 ─────────────────────────────────────────────────
section("Step 1: 环境变量检查")
required = ["OPENAI_API_KEY", "TAVILY_API_KEY"]
for key in required:
    val = os.environ.get(key, "")
    if val:
        ok(f"{key} = {val[:12]}...")
    else:
        fail(f"{key} 未设置")
        sys.exit(1)


# ─── Step 2: OpenAI 连通 ─────────────────────────────────────────────────
section("Step 2: OpenAI API 连通（gpt-4o-mini 单轮对话）")
async def test_openai():
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    info("发送: Hello, reply in one word")
    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Reply with one word: OK"}],
        max_tokens=10,
    )
    reply = resp.choices[0].message.content
    ok(f"OpenAI 响应: {reply!r}")

try:
    asyncio.run(test_openai())
except Exception as e:
    fail(f"OpenAI 连接失败: {e}")
    sys.exit(1)


# ─── Step 3: Tavily 搜索 ─────────────────────────────────────────────────
section("Step 3: Tavily 搜索 API")
async def test_tavily():
    from tavily import AsyncTavilyClient
    client = AsyncTavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    info("搜索: 字节跳动 前端工程师")
    results = await client.search("字节跳动 前端工程师", max_results=2)
    items = results.get("results", [])
    ok(f"Tavily 返回 {len(items)} 条结果")
    for r in items[:2]:
        info(f"  - {r.get('title', '')[:50]}")

try:
    asyncio.run(test_tavily())
except Exception as e:
    fail(f"Tavily 搜索失败: {e}")
    sys.exit(1)


# ─── Step 4: LangGraph 最小图（纯 Python，无 LLM）────────────────────────
section("Step 4: LangGraph 最小图（无 LLM，验证库可用）")
def test_langgraph_minimal():
    from typing import TypedDict
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint.memory import MemorySaver

    class MinState(TypedDict):
        value: int

    def add_one(state: MinState) -> dict:
        return {"value": state["value"] + 1}

    saver = MemorySaver()
    builder = StateGraph(MinState)
    builder.add_node("add", add_one)
    builder.set_entry_point("add")
    builder.add_edge("add", END)
    graph = builder.compile(checkpointer=saver)

    config = {"configurable": {"thread_id": "test-1"}}
    result = graph.invoke({"value": 0}, config)
    assert result["value"] == 1, f"期望 1，实际 {result['value']}"
    ok(f"LangGraph 最小图运行正常 → value=0 → {result['value']}")

try:
    test_langgraph_minimal()
except Exception as e:
    fail(f"LangGraph 初始化失败: {e}")
    sys.exit(1)


# ─── Step 5: 真实 research 图 search 节点 ───────────────────────────────
section("Step 5: 真实 search_node（Tavily + LangGraph 组合）")
async def test_research_search():
    from app.graphs.state import ResearchState
    from app.graphs.nodes import search_node

    state: ResearchState = {
        "job_id": "demo-001",
        "url": "https://www.zhipin.com/job_detail/demo.html",
        "title": "前端开发工程师",
        "company": "字节跳动",
        "requirements": ["React", "TypeScript"],
        "selected_directions": ["公司背景"],
        "jd_summary": "负责核心业务前端开发",
        "salary_range": "25k-50k",
        "location": "北京",
        "work_type": "全职",
        "search_results": {},
        "research_analysis": None,
        "draft_sections": None,
        "final_report": None,
        "human_feedback": [],
        "current_step": "search",
        "error": None,
        "resume_content": None,
        "report_data": None,
    }

    info("执行 search_node（Tavily 搜索公司背景）...")
    result = await search_node(state)
    sr = result.get("search_results", {})
    ok(f"search_node 完成 — current_step={result.get('current_step')}")
    for direction, items in sr.items():
        ok(f"  [{direction}] {len(items)} 条结果")
        for item in items[:2]:
            info(f"    - {item.get('title', '')[:60]}")

try:
    asyncio.run(test_research_search())
except Exception as e:
    fail(f"search_node 失败: {e}")
    import traceback; traceback.print_exc()
    sys.exit(1)


print(f"\n\033[1;32m{'='*60}\033[0m")
print(f"\033[1;32m  所有检查通过！LangGraph + 外部 API 均可用\033[0m")
print(f"\033[1;32m{'='*60}\033[0m\n")
