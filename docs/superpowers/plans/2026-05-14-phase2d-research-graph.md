# Phase 2D — LangGraph 研究图 + HiTL 过程审核 实施计划

**Goal:** 实现 LangGraph 多步调研 Agent 图，关键节点支持 Human-in-the-Loop interrupt，通过 SSE 推送进度/中断事件。用户在每个等待阶段可「直接编辑」或「带反馈重来」，LLM 基于累积的人类修正持续改进输出，最终生成结构化报告存入 DB。

**Architecture:** LangGraph `StateGraph` + `interrupt()` + Redis Pub/Sub SSE + 统一 `POST /resume` 恢复端点。Celery task 管理 graph 生命周期，graph 挂起时 checkpoint 到 MemorySaver。

**Tech Stack:** LangGraph · SQLAlchemy async · Redis Pub/Sub (SSE) · Celery · Tavily API · OpenAI gpt-4o · Python 3.12

---

## 状态机全貌

```
                              ┌──────────────────┐
                              │  用户反馈重来     │
                              │  POST /reparse    │
                              │  + feedback       │
                              └──────────────────┘
                                      ↑
                                      │
pending → parsing → awaiting_confirm ─┼─→ awaiting_directions
                      │              │          │
                      ↓ 直接编辑     │          ↓ POST /start
                 POST /confirm       │          │
                      │              │     ┌────┴────┐
                      └──────────────┘     │         │
                                          retry     start
                                      POST /dir     │
                                      + feedback    ↓
                                                  researching
                                                      │
                                              [LangGraph]
                                                      │
                                          ┌───────────┼───────────┐
                                          ↓           ↓           ↓
                                       search ──→ analyze ──→ generate ──→ done
                                                      │           │
                                                  ⏸ interrupt  ⏸ interrupt
                                                  review_       review_
                                                  results       draft
                                                      │           │
                                              POST /resume  POST /resume
                                              ┌───┼───┐     ┌───┼───┐
                                              ↓   ↓   ↓     ↓   ↓   ↓
                                          approve edit retry ...
```

---

## 文件结构

| 操作 | 路径 | 职责 |
|------|------|------|
| Create | `backend/app/graphs/__init__.py` | 空文件 |
| Create | `backend/app/graphs/state.py` | ResearchState TypedDict + 事件 schema |
| Create | `backend/app/graphs/research_graph.py` | 构建 StateGraph，interrupt 节点 + 图编译 |
| Create | `backend/app/graphs/nodes.py` | search / analyze / generate_report 节点 |
| Modify | `backend/app/tasks/research.py` | 实现 task_run_research：读 DB → 构建 state → astream |
| Modify | `backend/app/services/llm_service.py` | 新增 suggest_directions：LLM 根据 JD 建议调研方向 |
| Modify | `backend/app/api/v1/jobs.py` | 新增 POST /directions · /reparse · /resume 三个端点 |
| Create | `backend/tests/test_research_graph.py` | Graph 节点单元测试（mock LLM + Tavily） |
| Create | `backend/tests/test_resume_api.py` | resume / directions / reparse 端点集成测试 |

---

## Task 1 — ResearchState + 事件 Schema

**文件：** `backend/app/graphs/state.py`

```python
from typing import TypedDict


class ResearchState(TypedDict):
    """LangGraph 研究图全局状态，贯穿所有节点"""

    # ── 入口信息（从 DB Job 读入）──
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
    search_results: dict[str, list[dict]]  # direction → [{title, url, snippet}]
    research_analysis: str | None
    draft_sections: list[dict] | None  # [{direction, heading, content, sources}]
    final_report: str | None

    # ── 人类修正（累积）──
    # [{ node, action: "approve"|"edit"|"retry", edits, feedback }]
    human_feedback: list[dict]

    # ── 控制 ──
    current_step: str  # search / analyze / review_results / generate / review_draft / done
    error: str | None
```

**SSE 事件类型：**

| type | 触发时机 |
|---|---|
| `parsed` | LLM 解析 JD 完成（已有） |
| `error` | 任何步骤出错（已有） |
| `progress` | 每个 graph 节点开始执行 |
| `interrupt` | graph 挂起等待用户审核（含 node + data） |
| `completed` | 研究完成，final_report 已写 DB |

---

## Task 2 — 用户操作模型

每个等待阶段都是**「直接编辑」+「带反馈重来」**双通道，不引入通用 cancelled 状态。

### 2.1 各阶段操作一览

| 阶段 | 直接编辑 | 带反馈重来 | 端点 |
|---|---|---|---|
| `awaiting_confirm` | 改字段值 | 反馈错在哪，LLM 重新提取 | POST /confirm（已有）/ POST /reparse |
| `awaiting_directions` | 不需要（勾选即可） | 给方向提示，LLM 换一批建议 | POST /directions（新） |
| `review_results`（interrupt） | 修改分析文本 | 反馈哪里不够，重新分析 | POST /resume {edit\|retry} |
| `review_draft`（interrupt） | 修改段落内容 | 反馈修改意见，重新生成 | POST /resume {edit\|retry} |

### 2.2 统一的 resume payload

```python
class ResumePayload(BaseModel):
    action: str           # "approve" | "edit" | "retry"
    edits: dict | None    # action=edit 时传入，键值对覆盖 state 产出
    feedback: str | None  # action=retry 时可选传入，解释为何不满意
```

`feedback` 在 retry 时可选——用户可能说不出哪里不对，就是想让 LLM 再跑一次；也可能给出具体方向。

---

## Task 3 — 节点实现

**文件：** `backend/app/graphs/nodes.py`

### 3.1 search 节点

- 对 `selected_directions` 中每个方向调用 Tavily
- publish SSE `progress`
- 返回 `{"current_step": "analyze"}`

### 3.2 analyze 节点

- LLM 综合分析搜索结果 + JD 背景 + human_feedback
- 生成 `research_analysis`
- 返回 `{"current_step": "review_results"}`

**Prompt 构造要点（human_feedback 注入）：**

```
[System] 你是职位调研分析师...

[Job 信息] title / company / jd_summary / requirements

[搜索结果] direction → results...

[用户历史反馈]（若 human_feedback 非空）
  - [review_results] retry: "请重点分析远程办公政策"
  - [review_draft] edit: 修改了薪资部分的结论
请将这些意见纳入本次分析...
```

### 3.3 generate_report 节点

- LLM 基于 `research_analysis` + `search_results` + `human_feedback` 生成报告草稿
- 按方向分段，每段含关键发现 + 引用来源
- 返回 `{"draft_sections": [...], "current_step": "review_draft"}`

同样注入 human_feedback。

---

## Task 4 — LangGraph 图构建

**文件：** `backend/app/graphs/research_graph.py`

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt

from app.graphs.state import ResearchState
from app.graphs.nodes import search_node, analyze_node, generate_report_node


def _review_results(state: ResearchState) -> dict:
    """interrupt：用户审核搜索分析，可 approve / edit / retry"""
    interrupt({
        "type": "interrupt",
        "node": "review_results",
        "data": {
            "analysis": state["research_analysis"],
            "search_results": state["search_results"],
        },
    })
    # _handle_resume_action 根据 resume payload 决定下一步
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


def _handle_resume_action(state: ResearchState, retry_target: str, next_step: str) -> dict:
    """
    读取 human_feedback 最后一条的 action：
    - approve / edit → 继续 next_step
    - retry → 回到 retry_target 重新跑
    """
    fb = state["human_feedback"][-1] if state["human_feedback"] else {}
    if fb.get("action") == "retry":
        return {"current_step": retry_target}
    return {"current_step": next_step}


def _finalize(state: ResearchState) -> dict:
    return {"current_step": "done"}


def build_research_graph():
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
    builder.add_conditional_edges(
        "review_results",
        lambda s: s["current_step"],
        {"generate_report": "generate_report", "analyze": "analyze", "done": "finalize"},
    )
    builder.add_edge("generate_report", "review_draft")
    builder.add_conditional_edges(
        "review_draft",
        lambda s: s["current_step"],
        {"finalize": "finalize", "generate_report": "generate_report", "done": "finalize"},
    )
    builder.add_edge("finalize", END)

    return builder.compile(checkpointer=MemorySaver())
```

注意：interrupt 节点用**条件边**而非固定边路由——resume 时根据 action 决定是前进还是回退。

---

## Task 5 — task_run_research 实现

**文件：** `backend/app/tasks/research.py`

将占位替换为完整实现。关键设计：`resume` 参数区分首次运行和 checkpoint 恢复。

- **首次运行** (`resume=False`)：从 DB 构建 `initial_state`，传 `graph.astream(initial_state, config)`
- **恢复运行** (`resume=True`)：传 `graph.astream(None, config)`，LangGraph 自动从 checkpoint 恢复

```python
async def _build_initial_state(job_id: str) -> dict | None:
    """从 DB 构建 LangGraph 初始 state，首次运行时调用"""
    async with AsyncSessionLocal() as session:
        repo = JobRepository(session)
        job = await repo.get_by_id(job_id)
        if not job:
            return None
        return {
            "job_id": job_id,
            "url": job.url, "title": job.title,
            "company": job.company, "requirements": job.requirements or [],
            "selected_directions": job.selected_directions or [],
            "jd_summary": job.jd_summary or "",
            "salary_range": job.salary_range, "location": job.location,
            "work_type": job.work_type,
            "search_results": {}, "research_analysis": None,
            "draft_sections": None, "final_report": None,
            "human_feedback": [], "current_step": "search", "error": None,
        }


@celery_app.task(name="research.run", soft_time_limit=600)
def task_run_research(job_id: str, resume: bool = False) -> None:
    """LangGraph 研究图入口。resume=False 首次运行传 initial_state；resume=True 从 checkpoint 恢复传 None"""
    asyncio.run(_do_run_research(job_id, resume=resume))


async def _do_run_research(job_id: str, resume: bool = False) -> None:
    redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        from app.graphs.research_graph import build_research_graph
        graph = build_research_graph()
        config = {"configurable": {"thread_id": job_id}}

        # resume 时传 None，从 checkpoint 恢复；首次传 initial_state
        input_state = None if resume else await _build_initial_state(job_id)
        if input_state is None and not resume:
            return

        try:
            async for event in graph.astream(input_state, config):
                node_name = list(event.keys())[0]
                await redis.publish(
                    f"job:{job_id}",
                    json.dumps({"type": "progress", "node": node_name}),
                )
        except Exception as e:
            if "interrupt" in str(e).lower():
                return  # LangGraph interrupt，正常挂起
            raise

        # 正常结束，写 Report 到 DB
        final_state = graph.get_state(config)
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
            await redis.publish(
                f"job:{job_id}",
                json.dumps({"type": "completed"}),
            )

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

---

## Task 6 — 新增 API 端点

### 6.1 POST /jobs/{id}/directions

LLM 根据 JD 自动建议调研方向。

```python
class DirectionsResponse(BaseModel):
    suggestions: list[str]  # LLM 建议的方向，如 ["技术栈", "薪资竞争力", "团队文化"]


@router.post("/{job_id}/directions", response_model=DirectionsResponse)
async def suggest_directions(
    job_id: str,
    payload: DirectionsPayload | None = None,  # 可选 feedback
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """LLM 根据 JD 自动建议调研方向，用户可带 feedback 换一批"""
    repo = JobRepository(db)
    job = await repo.get_by_id(job_id)
    if not job: raise HTTPException(404)
    if job.user_id != current_user.id: raise HTTPException(403)

    from app.services.llm_service import suggest_directions as llm_suggest
    suggestions = await llm_suggest(
        title=job.title, company=job.company,
        jd_summary=job.jd_summary, requirements=job.requirements,
        feedback=payload.feedback if payload else None,
    )
    return DirectionsResponse(suggestions=suggestions)
```

### 6.2 POST /jobs/{id}/reparse

`awaiting_confirm` 阶段不满意 LLM 提取结果时调用。

```python
class ReparsePayload(BaseModel):
    feedback: str | None = None  # 指出上次提取哪里不对


@router.post("/{job_id}/reparse", response_model=JobResponse)
async def reparse_job(
    job_id: str,
    payload: ReparsePayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """重新触发 LLM 解析 JD，将 feedback 注入 prompt 改进提取质量"""
    repo = JobRepository(db)
    job = await repo.get_by_id(job_id)
    if not job: raise HTTPException(404)
    if job.user_id != current_user.id: raise HTTPException(403)
    if job.status != "awaiting_confirm": raise HTTPException(409)

    await repo.update_status(job_id, "parsing")
    # feedback 存入 Job 的 human_feedback 字段（若已有），Celery task 读它注入 prompt
    task_parse_jd.delay(job_id, feedback=payload.feedback)
    await db.refresh(job)
    return job
```

### 6.3 POST /jobs/{id}/resume

统一恢复端点，三种 action 覆盖所有 interrupt 场景。

```python
class ResumePayload(BaseModel):
    action: str       # "approve" | "edit" | "retry"
    edits: dict | None = None
    feedback: str | None = None


@router.post("/{job_id}/resume", response_model=JobDetailResponse)
async def resume_job(
    job_id: str,
    payload: ResumePayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = JobRepository(db)
    job = await repo.get_by_id(job_id)
    if not job: raise HTTPException(404)
    if job.user_id != current_user.id: raise HTTPException(403)
    if job.status != "researching": raise HTTPException(409)

    graph = build_research_graph()
    config = {"configurable": {"thread_id": job_id}}
    state = graph.get_state(config)

    # edit 场景：直接将 edits 写入 state 对应字段
    if payload.action == "edit" and payload.edits:
        updates = {}
        for key, value in payload.edits.items():
            if key in state.values:
                updates[key] = value
        await graph.aupdate_state(config, updates)

    # 追加 human_feedback
    feedback_entry = {
        "node": state.values.get("current_step", ""),
        "action": payload.action,
        "edits": payload.edits,
        "feedback": payload.feedback,
    }
    await graph.aupdate_state(config, {
        "human_feedback": state.values.get("human_feedback", []) + [feedback_entry],
    })

    task_run_research.delay(job_id, resume=True)
    return job
```

---

## Task 7 — LLMService 新增 suggest_directions

**文件：** `backend/app/services/llm_service.py`

```python
async def suggest_directions(
    title: str,
    company: str,
    jd_summary: str,
    requirements: list[str],
    feedback: str | None = None,
) -> list[str]:
    """根据 JD 自动建议调研方向，用户可通过 feedback 引导方向"""
    system_prompt = (
        "你是职位调研顾问。根据 JD 信息，建议 3-5 个调研方向。"
        "方向应覆盖：公司背景、技术栈、薪资、团队文化、面试经验等。"
        "返回 JSON：{\"directions\": [\"方向1\", \"方向2\"]}，不要多余内容。"
    )
    user_prompt = f"职位：{title}\n公司：{company}\n摘要：{jd_summary}\n要求：{requirements}"
    if feedback:
        user_prompt += f"\n\n用户反馈：{feedback}"

    resp = await chat(
        messages=[{"role": "system", "content": system_prompt},
                  {"role": "user", "content": user_prompt}],
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
    )
    return json.loads(resp)["directions"]
```

---

## Task 8 — 测试

**文件：** `backend/tests/test_research_graph.py`

- mock Tavily + LLM
- 验证 state 节点间流转
- 验证 interrupt 正确挂起
- 验证 retry 回退到正确节点
- 验证 human_feedback 累积

**文件：** `backend/tests/test_resume_api.py`

- 未鉴权 401 / 跨用户 403 / 状态不符 409
- approve → 继续执行
- edit → edits 写入 state
- retry + feedback → 回退 + feedback 记录

**文件：** `backend/tests/test_directions_api.py`

- LLM 返回建议列表
- feedback 引导方向变化

---

## 关键设计决策

1. **没有 cancelled 状态** — 每个阶段的「不满意」都用 retry 回流，用户始终可以调整而非终止
2. **直接编辑与反馈重来共存** — edit 适合小改，retry+feedback 适合 LLM 整体重跑
3. **human_feedback 累积注入所有 LLM prompt** — 每个节点都能看到完整人工干预历史
4. **interrupt 节点用条件边路由** — resume 时根据 action 决定前进还是回退
5. **MemorySaver 开发阶段** — Phase 3 迁 PostgresSaver

---

## 验证清单

- [ ] directions 端点：LLM 返回 3-5 个建议方向
- [ ] directions + feedback：方向列表随反馈变化
- [ ] reparse 端点：status 回 parsing，Celery task 触发
- [ ] resume { approve }：继续执行下一个节点
- [ ] resume { edit }：edits 写入 state，继续
- [ ] resume { retry }：回退到指定节点重新执行
- [ ] resume { retry, feedback }：feedback 写入 human_feedback，LLM prompt 包含反馈
- [ ] human_feedback 累积：两次 interrupt 的修正历史均在第三个 LLM 节点的 prompt 中
- [ ] SSE 事件：progress / interrupt / completed / error 全部正确推送
- [ ] search → analyze → review_results → generate → review_draft → finalize 全链路
