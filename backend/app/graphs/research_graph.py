"""LangGraph 研究图构建 — StateGraph + interrupt + 条件边路由"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.graphs.nodes import analyze_node, generate_report_node, search_node
from app.graphs.state import ResearchState

# ── 模块级单例 ─────────────────────────────────────────────
# MemorySaver 必须跨调用共享才能持久化 checkpoint。
# 生产环境迁 PostgresSaver（Phase 3）后此处改为 DB-backed checkpointer。
_saver: MemorySaver | None = None
_graph = None


def get_research_graph():
    """返回全局单例研究图。同一进程内多次调用共享同一个 MemorySaver。"""
    global _saver, _graph
    if _graph is None:
        _saver = MemorySaver()
        _graph = _build_graph(_saver)
    return _graph


def _build_graph(saver: MemorySaver):
    from langgraph.types import interrupt

    def _review_results(state: ResearchState) -> dict:
        """interrupt：用户审核搜索结果分析"""
        interrupt({
            "type": "interrupt",
            "node": "review_results",
            "data": {
                "analysis": state["research_analysis"],
                "search_results": state["search_results"],
            },
        })
        return _handle_resume_action(state, retry_target="analyze", next_step="generate_report")

    def _review_draft(state: ResearchState) -> dict:
        """interrupt：用户审核报告草稿"""
        interrupt({
            "type": "interrupt",
            "node": "review_draft",
            "data": {
                "draft_sections": state["draft_sections"],
            },
        })
        return _handle_resume_action(state, retry_target="generate_report", next_step="finalize")

    def _finalize(state: ResearchState) -> dict:
        """组装 final_report，不 publish SSE（由 task 层在 DB 写入后统一发送）"""
        sections = state.get("draft_sections") or []
        report = "\n\n".join(
            f"## {s.get('heading', '')}\n\n{s.get('content', '')}" for s in sections
        )
        return {"current_step": "done", "final_report": report}

    def _route_review_results(state: ResearchState) -> str:
        step = state.get("current_step", "")
        if step == "analyze":
            return "analyze"
        if step == "generate_report":
            return "generate_report"
        return "finalize"

    def _route_review_draft(state: ResearchState) -> str:
        step = state.get("current_step", "")
        if step == "generate_report":
            return "generate_report"
        return "finalize"

    builder = StateGraph(ResearchState)
    builder.add_node("search", search_node)
    builder.add_node("analyze", analyze_node)
    builder.add_node("review_results", _review_results)
    builder.add_node("generate_report", generate_report_node)
    builder.add_node("review_draft", _review_draft)
    builder.add_node("finalize", _finalize)

    builder.set_entry_point("search")
    builder.add_edge("search", "analyze")
    builder.add_edge("analyze", "review_results")
    builder.add_conditional_edges("review_results", _route_review_results, {
        "analyze": "analyze",
        "generate_report": "generate_report",
        "finalize": "finalize",
    })
    builder.add_edge("generate_report", "review_draft")
    builder.add_conditional_edges("review_draft", _route_review_draft, {
        "generate_report": "generate_report",
        "finalize": "finalize",
    })
    builder.add_edge("finalize", END)

    return builder.compile(checkpointer=saver)


def _handle_resume_action(state: ResearchState, retry_target: str, next_step: str) -> dict:
    fb = state["human_feedback"][-1] if state["human_feedback"] else {}
    if fb.get("action") == "retry":
        return {"current_step": retry_target}
    return {"current_step": next_step}
