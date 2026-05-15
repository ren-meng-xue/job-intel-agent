# Phase 2D BugFix — LangGraph 研究图稳定化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 Phase 2D LangGraph 研究图中六个已知缺陷，使 resume 流程可实际运行。

**Architecture:** 核心改动是架构重组：`MemorySaver` 改为模块级单例，所有 graph 状态操作从 API 层迁移到 Celery task 层，API `resume` 端点只负责将用户意图写入 Redis 并派发任务。`_finalize` 节点不再直接 publish SSE，由 task 层在 DB 写入后统一发送 `completed`。

**Tech Stack:** LangGraph >= 0.2 · FastAPI · Celery · Redis · Python 3.12

---

## 修复清单（按优先级）

| 优先级 | 问题 | 影响 |
|---|---|---|
| P0 | `MemorySaver` 非单例 — API 进程与 Celery 进程各建各的，checkpoint 不共享 | resume 流程完全无法工作 |
| P0 | `completed` SSE 事件双重发送 — `_finalize` 发一次，task 层又发一次 | 修完 P0-MemorySaver 后会触发 |
| P1 | `interrupt` 检测用 `"interrupt" in str(e)` 字符串匹配 | 版本升级后静默失效 |
| P1 | `graph.get_state()` 在 `async def` 中用同步版本 | 潜在 event loop 阻塞 |
| P2 | Redis 连接每个节点调用都 `from_url` + `aclose` | 连接频繁创建销毁 |
| P2 | `selected_directions` 为空时无防护 | 静默产出废报告 |

---

## 文件结构

| 操作 | 路径 | 变更说明 |
|---|---|---|
| Modify | `backend/app/graphs/research_graph.py` | `build_research_graph` → 模块级单例 `get_research_graph`；`_finalize` 去除 SSE publish 和 Redis 依赖 |
| Modify | `backend/app/api/v1/jobs.py` | `resume_job` 去掉 graph 交互，改为写 Redis + dispatch task |
| Modify | `backend/app/tasks/research.py` | 迁入所有 graph 状态操作；修复 `GraphInterrupt`；改用 `aget_state`；统一 `completed` 发送时机 |
| Modify | `backend/app/graphs/nodes.py` | 改用模块级 Redis 单例，避免每次 publish 创建新连接 |
| Create | `backend/tests/test_research_graph_bugfix.py` | 覆盖所有修复点的单元 + 集成测试 |

---

## Task 1 — `research_graph.py`：单例 + `_finalize` 去耦

**Files:**
- Modify: `backend/app/graphs/research_graph.py`

**背景：** `build_research_graph()` 每次调用都 `MemorySaver()` 一个新实例。API 进程和 Celery worker 进程各调一次，checkpoint 完全不共享。同时 `_finalize` 直接 publish SSE，与 task 层职责重叠造成双发。

- [ ] **Step 1: 完整替换 `research_graph.py`**

将文件内容替换为：

```python
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
```

- [ ] **Step 2: 验证导入无报错**

```bash
cd /Users/xuebao/learn/AI项目/job-intel-agent/backend
python -c "from app.graphs.research_graph import get_research_graph; g = get_research_graph(); print('OK', type(g))"
```

期望输出：`OK <class 'langgraph.graph.state.CompiledStateGraph'>` 或类似。

- [ ] **Step 3: 验证单例行为**

```bash
python -c "
from app.graphs.research_graph import get_research_graph
g1 = get_research_graph()
g2 = get_research_graph()
assert g1 is g2, 'NOT singleton!'
print('singleton OK')
"
```

---

## Task 2 — `api/v1/jobs.py`：resume 端点去掉 graph 交互

**Files:**
- Modify: `backend/app/api/v1/jobs.py:151-198`

**背景：** API 进程调 `build_research_graph()` 得到自己的 MemorySaver（空的），`get_state` 读到空状态，`aupdate_state` 更新也写在空 saver 里——对 Celery worker 进程的 saver 毫无影响。

修法：API 只负责把用户意图（action/edits/feedback）写入 Redis，Celery task 自己在有 checkpoint 的 saver 上操作。

- [ ] **Step 1: 替换 `resume_job` 端点**

找到 `jobs.py` 的 `resume_job` 函数（151-198 行），整体替换为：

```python
@router.post("/{job_id}/resume", response_model=JobDetailResponse)
async def resume_job(
    job_id: str,
    payload: ResumePayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """恢复 LangGraph 中断：将用户意图写入 Redis，由 Celery task 在 checkpoint 上应用"""
    if payload.action not in ("approve", "edit", "retry"):
        raise HTTPException(status_code=422, detail="action 须为 approve / edit / retry")

    repo = JobRepository(db)
    job = await repo.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    if job.status != "researching":
        raise HTTPException(status_code=409, detail=f"Job status is '{job.status}', expected 'researching'")

    import json
    import redis.asyncio as aioredis
    from app.core.config import settings

    redis_client = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    await redis_client.setex(
        f"job:{job_id}:resume_action",
        300,
        json.dumps({
            "action": payload.action,
            "edits": payload.edits,
            "feedback": payload.feedback,
        }),
    )
    await redis_client.aclose()

    task_run_research.delay(job_id, resume=True)
    return job
```

- [ ] **Step 2: 清理不再需要的导入**

在 `jobs.py` 顶部，确认 `build_research_graph` 相关导入已删除（如果有的话）。当前代码用 `from ... import` 在函数内部做的，检查并删除。

- [ ] **Step 3: 验证路由注册**

```bash
cd /Users/xuebao/learn/AI项目/job-intel-agent/backend
python -c "from app.api.v1.jobs import router; routes = [r.path for r in router.routes]; print(routes)"
```

期望输出包含 `/{job_id}/resume`。

---

## Task 3 — `tasks/research.py`：迁入所有 graph 操作

**Files:**
- Modify: `backend/app/tasks/research.py`

**背景：** 此处集中修复四个问题：
1. 使用 `get_research_graph()` 单例
2. 从 Redis 读取 resume action，在 Celery 进程内的 checkpoint 上应用
3. 用 `GraphInterrupt` 类型替换字符串匹配
4. 用 `await graph.aget_state()` 替换同步 `graph.get_state()`
5. `completed` 事件在 DB 写入后统一发送

- [ ] **Step 1: 替换整个 `_do_run_research` 函数**

将 `_do_run_research` 替换为（`task_parse_jd`、`_build_initial_state`、`task_run_research` 其他部分不变）：

```python
async def _do_run_research(job_id: str, resume: bool = False) -> None:
    redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        from langgraph.errors import GraphInterrupt

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
                    # LangGraph interrupt 事件：转发给 SSE 客户端
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
            # 部分 LangGraph 版本在 astream 外层抛出而非 yield __interrupt__ 事件
            for item in (exc.interrupts if hasattr(exc, "interrupts") else []):
                val = item.value if hasattr(item, "value") else item
                await redis.publish(f"job:{job_id}", json.dumps(val))
            return

        # stream 正常结束 → 检查是否完成（非 interrupted）
        final_state = await graph.aget_state(config)
        if final_state and not final_state.next:
            final_report = final_state.values.get("final_report") if final_state.values else None
            if final_report:
                from app.models.report import Report
                async with AsyncSessionLocal() as session:
                    report = Report(job_id=job_id, content=final_report, status="done")
                    session.add(report)
                    await session.commit()
                async with AsyncSessionLocal() as session:
                    repo = JobRepository(session)
                    await repo.update_status(job_id, "done")
                # completed 在 DB 写入后发送，保证前端拿到时数据已落库
                await redis.publish(f"job:{job_id}", json.dumps({"type": "completed"}))

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
```

- [ ] **Step 2: 验证模块导入**

```bash
cd /Users/xuebao/learn/AI项目/job-intel-agent/backend
python -c "from app.tasks.research import task_run_research, task_parse_jd; print('import OK')"
```

期望：`import OK`，无报错。

---

## Task 4 — `nodes.py`：Redis 连接池单例

**Files:**
- Modify: `backend/app/graphs/nodes.py`

**背景：** 每次 `_publish_progress` 调用都 `from_url` 创建新连接，一次研究流程中开关十几个 TCP 连接。改用模块级 Redis 单例（内部自带连接池）。

- [ ] **Step 1: 修改 `nodes.py` 顶部，替换 `_publish_progress`**

将文件头部的 Redis import 和 `_publish_progress` 函数替换为：

```python
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
```

- [ ] **Step 2: 验证节点可导入**

```bash
python -c "from app.graphs.nodes import search_node, analyze_node, generate_report_node; print('nodes OK')"
```

---

## Task 5 — 空 `selected_directions` 防护

**Files:**
- Modify: `backend/app/graphs/nodes.py`（`search_node` 函数）

**背景：** 用户若跳过 `/directions` 直接调 `/start` 且传空列表，`search_node` 迭代空列表，产出空 `search_results`，后续 LLM 分析毫无内容但不报错。

- [ ] **Step 1: 在 `search_node` 开头加防护**

将 `search_node` 函数的函数体第一行之后插入：

```python
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
    # ... 以下保持不变 ...
```

---

## Task 6 — 测试

**Files:**
- Create: `backend/tests/test_research_graph_bugfix.py`

- [ ] **Step 1: 创建测试文件**

```python
"""Phase 2D BugFix 验证测试"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Task 1: 单例测试 ────────────────────────────────────────

def test_get_research_graph_singleton():
    """同一进程两次调用返回同一个 graph 实例"""
    # 重置单例避免跨测试污染
    import app.graphs.research_graph as rg_module
    rg_module._graph = None
    rg_module._saver = None

    from app.graphs.research_graph import get_research_graph
    g1 = get_research_graph()
    g2 = get_research_graph()
    assert g1 is g2


def test_get_research_graph_has_checkpointer():
    """图必须挂载 MemorySaver"""
    import app.graphs.research_graph as rg_module
    rg_module._graph = None
    rg_module._saver = None

    from app.graphs.research_graph import get_research_graph
    graph = get_research_graph()
    assert graph.checkpointer is not None


# ── Task 5: 空 directions 防护 ───────────────────────────────

@pytest.mark.asyncio
async def test_search_node_empty_directions():
    """selected_directions 为空时返回 error 字段，不抛异常"""
    from app.graphs.nodes import search_node
    from app.graphs.state import ResearchState

    state: ResearchState = {
        "job_id": "test-job-1",
        "url": "https://example.com",
        "title": "Engineer",
        "company": "Acme",
        "requirements": [],
        "selected_directions": [],  # 空
        "jd_summary": "",
        "salary_range": None,
        "location": None,
        "work_type": None,
        "search_results": {},
        "research_analysis": None,
        "draft_sections": None,
        "final_report": None,
        "human_feedback": [],
        "current_step": "search",
        "error": None,
    }
    result = await search_node(state)
    assert result["search_results"] == {}
    assert result["error"] is not None
    assert "selected_directions" in result["error"]


# ── Task 3: resume action 从 Redis 读取 ────────────────────

@pytest.mark.asyncio
async def test_do_run_research_reads_resume_action_from_redis():
    """resume=True 时从 Redis 读取 action，读完删除 key"""
    import app.graphs.research_graph as rg_module
    rg_module._graph = None
    rg_module._saver = None

    action_payload = json.dumps({
        "action": "approve",
        "edits": None,
        "feedback": None,
    })

    mock_graph = MagicMock()
    mock_state = MagicMock()
    mock_state.values = {
        "current_step": "review_results",
        "human_feedback": [],
    }
    mock_state.next = []  # 模拟已完成（无 pending 节点）
    mock_graph.aget_state = AsyncMock(return_value=mock_state)
    mock_graph.aupdate_state = AsyncMock()
    mock_graph.astream = AsyncMock(return_value=aiter([]))

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=action_payload)
    mock_redis.delete = AsyncMock()
    mock_redis.publish = AsyncMock()
    mock_redis.aclose = AsyncMock()

    with patch("app.tasks.research.get_research_graph", return_value=mock_graph), \
         patch("aioredis.from_url", return_value=mock_redis):
        from app.tasks.research import _do_run_research
        await _do_run_research("test-job-1", resume=True)

    mock_redis.get.assert_called_once_with("job:test-job-1:resume_action")
    mock_redis.delete.assert_called_once_with("job:test-job-1:resume_action")


# ── Task 3: completed 只发一次 ───────────────────────────────

@pytest.mark.asyncio
async def test_completed_published_once_after_db_write():
    """completed 事件只在 DB 写入后发送一次，不重复"""
    import app.graphs.research_graph as rg_module
    rg_module._graph = None
    rg_module._saver = None

    mock_graph = MagicMock()
    mock_state = MagicMock()
    mock_state.values = {"final_report": "# Report", "human_feedback": []}
    mock_state.next = []  # 无 pending 节点 = 完成
    mock_graph.aget_state = AsyncMock(return_value=mock_state)
    mock_graph.astream = AsyncMock(return_value=aiter([{"finalize": {}}]))

    mock_redis = AsyncMock()
    mock_redis.publish = AsyncMock()
    mock_redis.aclose = AsyncMock()

    publish_calls = []
    async def record_publish(channel, message):
        publish_calls.append(json.loads(message))
    mock_redis.publish = record_publish

    with patch("app.tasks.research.get_research_graph", return_value=mock_graph), \
         patch("aioredis.from_url", return_value=mock_redis), \
         patch("app.tasks.research.AsyncSessionLocal") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session_cls.return_value = mock_session

        mock_repo = AsyncMock()
        with patch("app.tasks.research.JobRepository", return_value=mock_repo):
            from app.tasks.research import _do_run_research
            await _do_run_research("test-job-1", resume=False)

    completed_events = [e for e in publish_calls if e.get("type") == "completed"]
    assert len(completed_events) == 1, f"expected 1 completed event, got {len(completed_events)}"


def aiter(items):
    """同步列表转 async iterator，供 mock 使用"""
    async def _aiter():
        for item in items:
            yield item
    return _aiter()
```

- [ ] **Step 2: 运行测试**

```bash
cd /Users/xuebao/learn/AI项目/job-intel-agent/backend
python -m pytest tests/test_research_graph_bugfix.py -v
```

期望：所有测试 PASS。

- [ ] **Step 3: 运行完整测试套件，检查回归**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

期望：无新增 FAIL（原有失败不计入此次改动）。

---

## 验证清单

- [ ] `get_research_graph()` 两次调用返回同一实例
- [ ] `resume` 端点不再导入或调用 `build_research_graph`
- [ ] Redis key `job:{id}:resume_action` 在 Celery task 读取后被删除
- [ ] `GraphInterrupt` 用异常类型捕获，不依赖字符串匹配
- [ ] `aget_state` 替换所有同步 `get_state` 调用
- [ ] `completed` 事件在 DB 写入后发送，且仅发一次
- [ ] `search_node` 空 directions → 返回 error 字段，不抛异常
- [ ] 全套测试无回归
