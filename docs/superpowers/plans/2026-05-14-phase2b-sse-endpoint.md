# Phase 2B — SSE 推送端点 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 `GET /api/v1/reports/{job_id}/stream` SSE 端点，前端通过 `EventSource` 订阅指定 Job 的实时进度事件；后端订阅 Redis Pub/Sub channel `job:{job_id}`，将消息逐条以 SSE 格式推送；客户端断连时自动清理订阅。

**Architecture:** FastAPI `StreamingResponse` + `redis.asyncio` PubSub。鉴权通过 `get_current_user` 依赖注入；权限校验通过 `JobRepository.get_by_id` 查 DB（job.user_id 须等于 current_user.id，否则 403）；SSE generator 使用 `asyncio.wait_for` 超时逻辑检测客户端断连（generator 被 GC 时触发 `GeneratorExit`，在 `finally` 块中调用 `pubsub.unsubscribe` + `aclose`）。

**Tech Stack:** FastAPI, `redis.asyncio`, SQLAlchemy async, pytest + pytest-asyncio + unittest.mock

---

## 文件结构

| 操作 | 路径 | 职责 |
|------|------|------|
| Modify | `backend/app/api/v1/reports.py` | 实现 `stream_report` SSE 端点：鉴权、权限校验、Redis Pub/Sub 订阅、SSE 格式推送 |
| Create | `backend/tests/test_reports_sse.py` | SSE 端点集成测试：鉴权、权限校验、消息推送格式 |

---

### Task 1: 实现 SSE 端点

**Files:**
- Modify: `backend/app/api/v1/reports.py`

- [ ] **Step 1: 完整替换 `backend/app/api/v1/reports.py`**

```python
import asyncio
import json

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.repositories.job_repository import JobRepository
from app.schemas.report import ReportResponse
from app.services.auth_service import get_current_user

router = APIRouter()


async def _sse_generator(job_id: str):
    """
    订阅 Redis Pub/Sub channel `job:{job_id}`，将消息以 SSE 格式逐条 yield。
    客户端断连时（GeneratorExit），在 finally 块中清理订阅和 Redis 连接。
    每 15 秒发送一次 SSE keep-alive 注释行（`: keep-alive\n\n`），防止代理超时断连。
    """
    redis: aioredis.Redis = await aioredis.from_url(
        settings.REDIS_URL, decode_responses=True
    )
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"job:{job_id}")

    try:
        while True:
            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                    timeout=15.0,
                )
            except asyncio.TimeoutError:
                # 15 秒无消息 → 发送 keep-alive 注释，维持连接
                yield ": keep-alive\n\n"
                continue

            if message is None:
                # timeout=1.0 内无消息，继续等待
                await asyncio.sleep(0)
                continue

            data = message.get("data")
            if not isinstance(data, str):
                continue

            yield f"data: {data}\n\n"

            # 若事件类型为终态（parsed / error），主动关闭流
            try:
                parsed = json.loads(data)
                if parsed.get("type") in ("parsed", "error"):
                    break
            except (json.JSONDecodeError, AttributeError):
                pass

    except GeneratorExit:
        pass
    finally:
        await pubsub.unsubscribe(f"job:{job_id}")
        await pubsub.aclose()
        await redis.aclose()


@router.get("/{job_id}/stream")
async def stream_report(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    订阅 Redis Pub/Sub channel `job:{job_id}`，以 SSE 格式推送 Job 处理进度。

    - 需要登录鉴权（Bearer token）
    - 验证 job 属于当前用户（不属于返回 403）
    - 客户端断连时自动清理 Redis 订阅
    """
    repo = JobRepository(db)
    job = await repo.get_by_id(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail="Job 不存在")
    if job.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问该 Job")

    return StreamingResponse(
        _sse_generator(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 告知 Nginx 关闭缓冲，确保实时推送
        },
    )


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: str,
    current_user: User = Depends(get_current_user),
):
    # TODO: 从 DB 查询报告；status != done 时返回 202 ⚠️ 风险：content 大文本，注意序列化性能
    raise NotImplementedError
```

- [ ] **Step 2: 验证 Python 语法**

```bash
cd backend && python -c "from app.api.v1.reports import stream_report, _sse_generator; print('OK')"
```

Expected: `OK`

---

### Task 2: 编写测试

**Files:**
- Create: `backend/tests/test_reports_sse.py`

- [ ] **Step 1: 新建 `backend/tests/test_reports_sse.py`**

```python
"""
SSE 端点测试 — GET /api/v1/reports/{job_id}/stream

测试策略：
- 用 unittest.mock patch 掉 `app.api.v1.reports.aioredis`，避免真实 Redis 连接
- 用 AsyncMock 模拟 pubsub.get_message 返回指定消息序列
- 通过 httpx AsyncClient 发起请求，读取 StreamingResponse 内容
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


# ---------- 辅助函数 ----------


async def _register_and_login(client: AsyncClient, suffix: str = "") -> dict:
    """注册并登录，返回 Authorization header dict"""
    email = f"sse{suffix}@example.com"
    username = f"sseuser{suffix}"
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


async def _create_job(client: AsyncClient, headers: dict) -> str:
    """创建 Job，返回 job_id；patch 掉 Celery task 避免真实调用"""
    with patch("app.api.v1.jobs.task_parse_jd") as mock_task:
        mock_task.delay = lambda job_id: None
        resp = await client.post(
            "/api/v1/jobs/",
            json={"url": "https://example.com/job"},
            headers=headers,
        )
    assert resp.status_code == 201
    return resp.json()["id"]


def _make_mock_pubsub(messages: list[dict | None]):
    """
    构造一个 Mock PubSub，get_message 按顺序返回 messages 列表中的元素，
    列表耗尽后始终返回 None（触发 keep-alive 或超时）。
    """
    call_count = 0
    get_message_results = list(messages)

    async def fake_get_message(**kwargs):
        nonlocal call_count
        if call_count < len(get_message_results):
            result = get_message_results[call_count]
            call_count += 1
            return result
        # 后续调用抛出 asyncio.TimeoutError 触发 keep-alive 后 break
        import asyncio
        raise asyncio.TimeoutError

    pubsub = MagicMock()
    pubsub.subscribe = AsyncMock()
    pubsub.unsubscribe = AsyncMock()
    pubsub.aclose = AsyncMock()
    pubsub.get_message = fake_get_message
    return pubsub


def _make_mock_redis(pubsub):
    """构造 Mock Redis，from_url 返回 mock_redis，mock_redis.pubsub() 返回 pubsub"""
    mock_redis = MagicMock()
    mock_redis.pubsub = MagicMock(return_value=pubsub)
    mock_redis.aclose = AsyncMock()
    return mock_redis


# ---------- 测试用例 ----------


async def test_stream_requires_auth(client: AsyncClient):
    """未提供 token 时返回 401"""
    resp = await client.get("/api/v1/reports/nonexistent-job-id/stream")
    assert resp.status_code == 401


async def test_stream_returns_404_for_nonexistent_job(client: AsyncClient):
    """Job 不存在时返回 404"""
    headers = await _register_and_login(client, suffix="404")
    pubsub = _make_mock_pubsub([])
    mock_redis = _make_mock_redis(pubsub)

    with patch("app.api.v1.reports.aioredis") as mock_aioredis_mod:
        mock_aioredis_mod.from_url = AsyncMock(return_value=mock_redis)
        resp = await client.get(
            "/api/v1/reports/nonexistent-job-id/stream",
            headers=headers,
        )

    assert resp.status_code == 404


async def test_stream_returns_403_for_other_users_job(client: AsyncClient):
    """访问其他用户的 Job 返回 403"""
    # 用户 A 创建 Job
    headers_a = await _register_and_login(client, suffix="a403")
    job_id = await _create_job(client, headers_a)

    # 用户 B 尝试订阅
    headers_b = await _register_and_login(client, suffix="b403")
    pubsub = _make_mock_pubsub([])
    mock_redis = _make_mock_redis(pubsub)

    with patch("app.api.v1.reports.aioredis") as mock_aioredis_mod:
        mock_aioredis_mod.from_url = AsyncMock(return_value=mock_redis)
        resp = await client.get(
            f"/api/v1/reports/{job_id}/stream",
            headers=headers_b,
        )

    assert resp.status_code == 403


async def test_stream_returns_sse_content_type(client: AsyncClient):
    """正常请求返回 text/event-stream Content-Type"""
    headers = await _register_and_login(client, suffix="ct")
    job_id = await _create_job(client, headers)

    # 第一条消息即为终态，generator 立即退出
    parsed_event = json.dumps({"type": "parsed", "title": "SWE", "company": "Acme"})
    pubsub = _make_mock_pubsub([
        {"type": "message", "data": parsed_event},
    ])
    mock_redis = _make_mock_redis(pubsub)

    with patch("app.api.v1.reports.aioredis") as mock_aioredis_mod:
        mock_aioredis_mod.from_url = AsyncMock(return_value=mock_redis)
        resp = await client.get(
            f"/api/v1/reports/{job_id}/stream",
            headers=headers,
        )

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]


async def test_stream_pushes_parsed_event(client: AsyncClient):
    """推送 parsed 事件后 SSE body 包含正确 data 行"""
    headers = await _register_and_login(client, suffix="push")
    job_id = await _create_job(client, headers)

    payload = {"type": "parsed", "title": "Backend Engineer", "company": "TechCorp"}
    parsed_event = json.dumps(payload)
    pubsub = _make_mock_pubsub([
        {"type": "message", "data": parsed_event},
    ])
    mock_redis = _make_mock_redis(pubsub)

    with patch("app.api.v1.reports.aioredis") as mock_aioredis_mod:
        mock_aioredis_mod.from_url = AsyncMock(return_value=mock_redis)
        resp = await client.get(
            f"/api/v1/reports/{job_id}/stream",
            headers=headers,
        )

    assert resp.status_code == 200
    body = resp.text
    # SSE 格式：data: {json}\n\n
    assert f"data: {parsed_event}" in body
    # 验证 JSON 内容可正确解析
    for line in body.splitlines():
        if line.startswith("data:"):
            data_str = line[len("data:"):].strip()
            data = json.loads(data_str)
            assert data["type"] == "parsed"
            assert data["title"] == "Backend Engineer"
            break


async def test_stream_pushes_error_event(client: AsyncClient):
    """推送 error 事件后 SSE body 包含 type=error"""
    headers = await _register_and_login(client, suffix="err")
    job_id = await _create_job(client, headers)

    error_payload = {"type": "error", "job_id": job_id}
    error_event = json.dumps(error_payload)
    pubsub = _make_mock_pubsub([
        {"type": "message", "data": error_event},
    ])
    mock_redis = _make_mock_redis(pubsub)

    with patch("app.api.v1.reports.aioredis") as mock_aioredis_mod:
        mock_aioredis_mod.from_url = AsyncMock(return_value=mock_redis)
        resp = await client.get(
            f"/api/v1/reports/{job_id}/stream",
            headers=headers,
        )

    assert resp.status_code == 200
    body = resp.text
    assert "data:" in body
    for line in body.splitlines():
        if line.startswith("data:"):
            data = json.loads(line[len("data:"):].strip())
            assert data["type"] == "error"
            break


async def test_stream_subscribes_to_correct_channel(client: AsyncClient):
    """验证订阅了正确的 channel: job:{job_id}"""
    headers = await _register_and_login(client, suffix="ch")
    job_id = await _create_job(client, headers)

    parsed_event = json.dumps({"type": "parsed", "title": "SWE", "company": "X"})
    pubsub = _make_mock_pubsub([
        {"type": "message", "data": parsed_event},
    ])
    mock_redis = _make_mock_redis(pubsub)

    with patch("app.api.v1.reports.aioredis") as mock_aioredis_mod:
        mock_aioredis_mod.from_url = AsyncMock(return_value=mock_redis)
        await client.get(
            f"/api/v1/reports/{job_id}/stream",
            headers=headers,
        )

    pubsub.subscribe.assert_called_once_with(f"job:{job_id}")


async def test_stream_cleans_up_on_completion(client: AsyncClient):
    """流结束后验证 unsubscribe 和 aclose 均被调用（资源已释放）"""
    headers = await _register_and_login(client, suffix="cleanup")
    job_id = await _create_job(client, headers)

    parsed_event = json.dumps({"type": "parsed", "title": "SWE", "company": "X"})
    pubsub = _make_mock_pubsub([
        {"type": "message", "data": parsed_event},
    ])
    mock_redis = _make_mock_redis(pubsub)

    with patch("app.api.v1.reports.aioredis") as mock_aioredis_mod:
        mock_aioredis_mod.from_url = AsyncMock(return_value=mock_redis)
        await client.get(
            f"/api/v1/reports/{job_id}/stream",
            headers=headers,
        )

    pubsub.unsubscribe.assert_called_once_with(f"job:{job_id}")
    pubsub.aclose.assert_called_once()
    mock_redis.aclose.assert_called_once()
```

- [ ] **Step 2: 运行测试，确认全部通过**

```bash
cd backend && python -m pytest tests/test_reports_sse.py -v
```

Expected: 8 tests PASSED

- [ ] **Step 3: 运行全量测试，确认无回归**

```bash
cd backend && python -m pytest -v
```

Expected: 全部 PASSED（含 auth / job / reports_sse 测试）

---

### Task 3: Commit

- [ ] **Step 1: Commit 实现代码和测试**

```bash
git add backend/app/api/v1/reports.py backend/tests/test_reports_sse.py
git commit -m "feat: 实现 GET /api/v1/reports/{job_id}/stream — SSE 推送 Job 进度"
```

---

## 自我审查

**Spec 覆盖检查：**
- ✅ `GET /api/v1/reports/{job_id}/stream` 路由 → Task 1（`stream_report`）
- ✅ 订阅 Redis Pub/Sub channel `job:{job_id}` → Task 1（`_sse_generator` 中 `pubsub.subscribe`）
- ✅ 以 SSE 格式逐条推送（`data: {json}\n\n`）→ Task 1（`yield f"data: {data}\n\n"`）
- ✅ 客户端断连时清理订阅 → Task 1（`finally` 块 `unsubscribe` + `aclose`）
- ✅ 需要登录鉴权 → Task 1（`Depends(get_current_user)`）
- ✅ 验证 Job 属于当前用户，否则 403 → Task 1（`job.user_id != current_user.id` → 403）
- ✅ 测试：未鉴权 401 → Task 2（`test_stream_requires_auth`）
- ✅ 测试：Job 不存在 404 → Task 2（`test_stream_returns_404_for_nonexistent_job`）
- ✅ 测试：跨用户 403 → Task 2（`test_stream_returns_403_for_other_users_job`）
- ✅ 测试：正确 SSE Content-Type → Task 2（`test_stream_returns_sse_content_type`）
- ✅ 测试：parsed 事件格式 → Task 2（`test_stream_pushes_parsed_event`）
- ✅ 测试：error 事件格式 → Task 2（`test_stream_pushes_error_event`）
- ✅ 测试：订阅正确 channel → Task 2（`test_stream_subscribes_to_correct_channel`）
- ✅ 测试：资源清理 → Task 2（`test_stream_cleans_up_on_completion`）

**类型一致性：**
- `JobRepository.get_by_id(job_id)` 在 `job_repository.py` 定义，`stream_report` 中调用签名一致
- `get_current_user` 依赖注入来自 `app.services.auth_service`，与其他路由一致
- `_sse_generator` 使用 `aioredis.from_url(settings.REDIS_URL, decode_responses=True)` 与 `app/core/redis.py` 中配置一致

**边界情况处理：**
- `get_message` 返回 `None`（无新消息）→ `await asyncio.sleep(0)` 让出控制权后继续循环，不阻塞事件循环
- `get_message` 超时（15 秒）→ 发送 keep-alive 注释行，防止代理（Nginx / CDN）超时断开
- `data` 字段非字符串（如 subscribe 确认消息的整数计数）→ `ignore_subscribe_messages=True` + `isinstance(data, str)` 双重过滤
- 终态事件（`parsed` / `error`）→ `break` 主动结束 generator，避免连接空挂
