"""
Phase 2D bugfix 测试 — 覆盖 LangGraph 研究图修复的六个关键点

1. get_research_graph 单例：两次调用同一实例 + checkpointer 不为 None
2. search_node 空 selected_directions 早退：返回 error 字段，search_results 为空字典
3. resume_job 端点写 Redis：setex 调用正确 + 非法 action 返回 422
4. _do_run_research resume 流程读 Redis：get + delete 均被调用
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─────────────────────────────────────────────────────────────────
# 1. get_research_graph 单例
# ─────────────────────────────────────────────────────────────────


def _reset_graph_module():
    """重置模块级单例，保证每个测试独立"""
    import app.graphs.research_graph as rg
    rg._graph = None
    rg._saver = None


def test_get_research_graph_returns_singleton():
    """两次调用 get_research_graph 返回同一实例"""
    _reset_graph_module()
    from app.graphs.research_graph import get_research_graph

    g1 = get_research_graph()
    g2 = get_research_graph()
    assert g1 is g2, "两次调用应返回同一图实例"


def test_get_research_graph_has_checkpointer():
    """编译后的图挂载了 checkpointer（不为 None）"""
    _reset_graph_module()
    from app.graphs.research_graph import get_research_graph

    graph = get_research_graph()
    # LangGraph CompiledGraph 将 checkpointer 存在 checkpointer 属性上
    assert hasattr(graph, "checkpointer"), "图对象应有 checkpointer 属性"
    assert graph.checkpointer is not None, "checkpointer 不应为 None"


# ─────────────────────────────────────────────────────────────────
# 2. search_node 空 selected_directions 早退
# ─────────────────────────────────────────────────────────────────


async def test_search_node_empty_directions_returns_error():
    """selected_directions=[] 时应立即返回 error，不调用 search"""
    from app.graphs.nodes import search_node

    state = {
        "job_id": "j-test",
        "url": "https://example.com",
        "title": "SWE",
        "company": "Acme",
        "requirements": ["Python"],
        "selected_directions": [],   # 关键：空列表
        "jd_summary": "Great role",
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

    with patch("app.graphs.nodes.search") as mock_search:
        mock_search.side_effect = AssertionError("search 不应被调用")
        result = await search_node(state)

    assert "error" in result, "返回值应包含 error 字段"
    assert result["error"], "error 字段不应为空"
    assert result["search_results"] == {}, "search_results 应为空字典"


async def test_search_node_empty_directions_no_exception():
    """selected_directions=[] 时不抛异常"""
    from app.graphs.nodes import search_node

    state = {
        "job_id": "j-test",
        "url": "https://example.com",
        "title": "SWE",
        "company": "Acme",
        "requirements": [],
        "selected_directions": [],
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

    # 不应抛出任何异常，且 search 不应被调用（空 directions 早退）
    with patch("app.graphs.nodes.search") as mock_search:
        result = await search_node(state)

    assert isinstance(result, dict), "返回值应为 dict"
    assert result.get("search_results") == {}
    mock_search.assert_not_called()  # Q1: 验证 Tavily 未被调用


# ─────────────────────────────────────────────────────────────────
# 3. resume_job 端点写 Redis
# ─────────────────────────────────────────────────────────────────


async def _register_and_login_for_resume(client, suffix: str = "") -> dict:
    """注册并登录，返回 Auth header"""
    from httpx import AsyncClient
    email = f"resume{suffix}@example.com"
    username = f"resumeuser{suffix}"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": "password123"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _create_researching_job(client, headers: dict) -> str:
    """创建一个处于 researching 状态的 job（通过直接操控 mock）"""
    # 1. 创建 job（status=parsing）
    with patch("app.api.v1.jobs.task_parse_jd") as mock_task:
        mock_task.delay = lambda job_id: None
        resp = await client.post(
            "/api/v1/jobs/",
            json={"url": "https://example.com/job"},
            headers=headers,
        )
    assert resp.status_code == 201
    job_id = resp.json()["id"]
    return job_id


async def test_resume_job_writes_redis_setex(client):
    """POST /{job_id}/resume 应调用 Redis setex，key 正确，TTL=300"""
    headers = await _register_and_login_for_resume(client, suffix="setex")
    job_id = await _create_researching_job(client, headers)

    # 直接操作 DB 把 job status 改为 researching
    from app.core.database import get_db
    from app.main import app

    # 通过 API 依赖中已注入的测试 DB 修改 job status
    db_override = app.dependency_overrides.get(get_db)
    assert db_override is not None
    async for db in db_override():
        from sqlalchemy import text
        await db.execute(
            text("UPDATE jobs SET status = 'researching' WHERE id = :id"),
            {"id": job_id},
        )
        await db.commit()
        break

    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()
    mock_redis.aclose = AsyncMock()

    with (
        patch("app.api.v1.jobs.aioredis") as mock_aioredis,
        patch("app.api.v1.jobs.task_run_research") as mock_task,
    ):
        mock_aioredis.from_url = AsyncMock(return_value=mock_redis)
        mock_task.delay = MagicMock()

        resp = await client.post(
            f"/api/v1/jobs/{job_id}/resume",
            json={"action": "approve"},
            headers=headers,
        )

    assert resp.status_code == 200, f"期望 200，实际: {resp.status_code}, body: {resp.text}"

    # 验证 setex 被正确调用
    mock_redis.setex.assert_called_once()
    call_args = mock_redis.setex.call_args

    # 第一个位置参数是 key
    key = call_args[0][0] if call_args[0] else call_args[1].get("name")
    assert key == f"job:{job_id}:resume_action", f"key 不匹配: {key}"

    # 第二个位置参数是 TTL
    ttl = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("time")
    assert ttl == 300, f"TTL 应为 300，实际: {ttl}"

    # 第三个位置参数是 value，应为 JSON
    value_str = call_args[0][2] if len(call_args[0]) > 2 else call_args[1].get("value")
    value = json.loads(value_str)
    assert value["action"] == "approve"


async def test_resume_job_invalid_action_returns_422(client):
    """action 非法值（非 approve/edit/retry）应返回 422"""
    headers = await _register_and_login_for_resume(client, suffix="422")

    # action 校验在 DB 查询前（jobs.py resume_job 入口处先校验 action），故无需 mock DB（Q4）
    # 传入非法 action，FastAPI 在路由层做 Literal 校验，直接返回 422，不会走到 DB 查询
    resp = await client.post(
        "/api/v1/jobs/nonexistent-job-id/resume",
        json={"action": "invalid_action"},
        headers=headers,
    )
    assert resp.status_code == 422, f"期望 422，实际: {resp.status_code}"


async def test_resume_job_task_is_called_with_resume_true(client):
    """POST /{job_id}/resume 应触发 task_run_research.delay(job_id, resume=True)"""
    headers = await _register_and_login_for_resume(client, suffix="task")
    job_id = await _create_researching_job(client, headers)

    # 把 job status 改为 researching
    from app.core.database import get_db
    from app.main import app

    db_override = app.dependency_overrides.get(get_db)
    async for db in db_override():
        from sqlalchemy import text
        await db.execute(
            text("UPDATE jobs SET status = 'researching' WHERE id = :id"),
            {"id": job_id},
        )
        await db.commit()
        break

    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()
    mock_redis.aclose = AsyncMock()

    with (
        patch("app.api.v1.jobs.aioredis") as mock_aioredis,
        patch("app.api.v1.jobs.task_run_research") as mock_task,
    ):
        mock_aioredis.from_url = AsyncMock(return_value=mock_redis)
        mock_task.delay = MagicMock()

        resp = await client.post(
            f"/api/v1/jobs/{job_id}/resume",
            json={"action": "retry", "feedback": "请重试"},
            headers=headers,
        )

    assert resp.status_code == 200
    mock_task.delay.assert_called_once_with(job_id, resume=True)


# ─────────────────────────────────────────────────────────────────
# 4. _do_run_research resume 流程读 Redis
# ─────────────────────────────────────────────────────────────────


def _make_run_research_mocks(action_data_json=None):
    """构造 _do_run_research 测试所需的通用 mock 对象"""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=action_data_json)
    mock_redis.delete = AsyncMock()
    mock_redis.publish = AsyncMock()
    mock_redis.aclose = AsyncMock()

    mock_state = MagicMock()
    mock_state.values = {"current_step": "review_results", "human_feedback": []}
    mock_state.next = []

    mock_graph = AsyncMock()
    mock_graph.aget_state = AsyncMock(return_value=mock_state)
    mock_graph.aupdate_state = AsyncMock()
    mock_graph.astream = MagicMock(return_value=_async_iter([
        {"__interrupt__": [MagicMock(value={"type": "interrupt", "node": "review_results", "data": {}})]}
    ]))

    return mock_redis, mock_graph


async def _run_with_mocks(job_id: str, resume: bool, mock_redis, mock_graph):
    """执行 _do_run_research，并注入 mock_redis 和 mock_graph"""
    from app.tasks.research import _do_run_research

    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=MagicMock())
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    # _do_run_research 内部通过 `from app.graphs.research_graph import get_research_graph`
    # 局部导入，patch 源模块属性确保自动恢复（Q3）
    with (
        patch("app.graphs.research_graph.get_research_graph", return_value=mock_graph),
        patch("app.tasks.research.aioredis") as mock_aioredis_mod,
        patch("app.tasks.research.AsyncSessionLocal", return_value=mock_session_ctx),
    ):
        mock_aioredis_mod.from_url = AsyncMock(return_value=mock_redis)
        await _do_run_research(job_id, resume=resume)


async def test_do_run_research_resume_calls_redis_get():
    """resume=True 时应调用 redis.get("job:{id}:resume_action")"""
    job_id = "j-resume-test"
    action_data = {"action": "approve"}
    mock_redis, mock_graph = _make_run_research_mocks(json.dumps(action_data))

    await _run_with_mocks(job_id, resume=True, mock_redis=mock_redis, mock_graph=mock_graph)

    # 验证 get 被调用，key 正确
    mock_redis.get.assert_called_once_with(f"job:{job_id}:resume_action")


async def test_do_run_research_resume_calls_redis_delete_after_get():
    """resume=True 时读取 redis key 后应调用 delete 清理"""
    job_id = "j-delete-test"
    action_data = {"action": "approve"}
    mock_redis, mock_graph = _make_run_research_mocks(json.dumps(action_data))

    await _run_with_mocks(job_id, resume=True, mock_redis=mock_redis, mock_graph=mock_graph)

    # 验证 delete 被调用，key 正确
    mock_redis.delete.assert_called_once_with(f"job:{job_id}:resume_action")


async def test_do_run_research_resume_skips_get_when_no_key():
    """resume=True 但 Redis 中无对应 key 时（get 返回 None），不调用 aupdate_state 写入 feedback"""
    job_id = "j-no-key"
    # action_data_json=None 模拟 Redis 中无 key
    mock_redis, mock_graph = _make_run_research_mocks(action_data_json=None)

    await _run_with_mocks(job_id, resume=True, mock_redis=mock_redis, mock_graph=mock_graph)

    # get 被调用，但 delete 不应被调用（因为 raw 为 None，走不到 delete）
    mock_redis.get.assert_called_once_with(f"job:{job_id}:resume_action")
    mock_redis.delete.assert_not_called()
    # aupdate_state 写 feedback 也不应被调用
    mock_graph.aupdate_state.assert_not_called()


# ─────────────────────────────────────────────────────────────────
# 辅助：异步迭代器 helper
# ─────────────────────────────────────────────────────────────────


async def _async_iter_gen(items):
    for item in items:
        yield item


def _async_iter(items):
    """返回一个异步迭代器，用于 mock astream"""
    return _async_iter_gen(items)
