"""
SSE 端点测试 — GET /api/v1/reports/{job_id}/stream

测试策略：用 unittest.mock patch aioredis，AsyncMock 模拟 pubsub 消息序列，
通过 httpx AsyncClient 请求 StreamingResponse 并验证 body 内容。
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


# ---------- helpers ----------


async def _register_and_login(client: AsyncClient, suffix: str = "") -> dict:
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
    with patch("app.api.v1.jobs.task_parse_jd") as mock_task:
        mock_task.delay = lambda job_id: None
        resp = await client.post(
            "/api/v1/jobs/",
            json={"url": "https://example.com/job"},
            headers=headers,
        )
    assert resp.status_code == 201
    return resp.json()["id"]


def _make_mock_pubsub(messages: list):
    """构造 Mock PubSub，get_message 按 messages 列表顺序返回，耗尽后抛 TimeoutError"""
    call_count = 0
    results = list(messages)

    async def fake_get_message(**kwargs):
        nonlocal call_count
        if call_count < len(results):
            result = results[call_count]
            call_count += 1
            return result
        import asyncio
        raise asyncio.TimeoutError

    pubsub = MagicMock()
    pubsub.subscribe = AsyncMock()
    pubsub.unsubscribe = AsyncMock()
    pubsub.aclose = AsyncMock()
    pubsub.get_message = fake_get_message
    return pubsub


def _make_mock_redis(pubsub):
    mock_redis = MagicMock()
    mock_redis.pubsub = MagicMock(return_value=pubsub)
    mock_redis.aclose = AsyncMock()
    return mock_redis


# ---------- tests ----------


async def test_stream_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/reports/nonexistent-job-id/stream")
    assert resp.status_code == 401


async def test_stream_returns_404_for_nonexistent_job(client: AsyncClient):
    headers = await _register_and_login(client, suffix="404")
    pubsub = _make_mock_pubsub([])
    mock_redis = _make_mock_redis(pubsub)

    with patch("app.api.v1.reports.aioredis") as mock_mod:
        mock_mod.from_url = AsyncMock(return_value=mock_redis)
        resp = await client.get(
            "/api/v1/reports/00000000-0000-0000-0000-000000000000/stream",
            headers=headers,
        )

    assert resp.status_code == 404


async def test_stream_returns_403_for_other_users_job(client: AsyncClient):
    headers_a = await _register_and_login(client, suffix="a403")
    job_id = await _create_job(client, headers_a)

    headers_b = await _register_and_login(client, suffix="b403")
    pubsub = _make_mock_pubsub([])
    mock_redis = _make_mock_redis(pubsub)

    with patch("app.api.v1.reports.aioredis") as mock_mod:
        mock_mod.from_url = AsyncMock(return_value=mock_redis)
        resp = await client.get(
            f"/api/v1/reports/{job_id}/stream",
            headers=headers_b,
        )

    assert resp.status_code == 403


async def test_stream_returns_sse_content_type(client: AsyncClient):
    headers = await _register_and_login(client, suffix="ct")
    job_id = await _create_job(client, headers)

    parsed_event = json.dumps({"type": "parsed", "title": "SWE", "company": "Acme"})
    pubsub = _make_mock_pubsub([{"type": "message", "data": parsed_event}])
    mock_redis = _make_mock_redis(pubsub)

    with patch("app.api.v1.reports.aioredis") as mock_mod:
        mock_mod.from_url = AsyncMock(return_value=mock_redis)
        resp = await client.get(
            f"/api/v1/reports/{job_id}/stream",
            headers=headers,
        )

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]


async def test_stream_pushes_parsed_event(client: AsyncClient):
    headers = await _register_and_login(client, suffix="push")
    job_id = await _create_job(client, headers)

    payload = {"type": "parsed", "title": "Backend Engineer", "company": "TechCorp"}
    parsed_event = json.dumps(payload)
    pubsub = _make_mock_pubsub([{"type": "message", "data": parsed_event}])
    mock_redis = _make_mock_redis(pubsub)

    with patch("app.api.v1.reports.aioredis") as mock_mod:
        mock_mod.from_url = AsyncMock(return_value=mock_redis)
        resp = await client.get(
            f"/api/v1/reports/{job_id}/stream",
            headers=headers,
        )

    assert resp.status_code == 200
    assert f"data: {parsed_event}" in resp.text
    for line in resp.text.splitlines():
        if line.startswith("data:"):
            data = json.loads(line[len("data:"):].strip())
            assert data["type"] == "parsed"
            assert data["title"] == "Backend Engineer"
            break


async def test_stream_pushes_error_event(client: AsyncClient):
    headers = await _register_and_login(client, suffix="err")
    job_id = await _create_job(client, headers)

    error_event = json.dumps({"type": "error", "job_id": job_id})
    pubsub = _make_mock_pubsub([{"type": "message", "data": error_event}])
    mock_redis = _make_mock_redis(pubsub)

    with patch("app.api.v1.reports.aioredis") as mock_mod:
        mock_mod.from_url = AsyncMock(return_value=mock_redis)
        resp = await client.get(
            f"/api/v1/reports/{job_id}/stream",
            headers=headers,
        )

    assert resp.status_code == 200
    for line in resp.text.splitlines():
        if line.startswith("data:"):
            data = json.loads(line[len("data:"):].strip())
            assert data["type"] == "error"
            break


async def test_stream_subscribes_to_correct_channel(client: AsyncClient):
    headers = await _register_and_login(client, suffix="ch")
    job_id = await _create_job(client, headers)

    parsed_event = json.dumps({"type": "parsed", "title": "SWE", "company": "X"})
    pubsub = _make_mock_pubsub([{"type": "message", "data": parsed_event}])
    mock_redis = _make_mock_redis(pubsub)

    with patch("app.api.v1.reports.aioredis") as mock_mod:
        mock_mod.from_url = AsyncMock(return_value=mock_redis)
        await client.get(
            f"/api/v1/reports/{job_id}/stream",
            headers=headers,
        )

    pubsub.subscribe.assert_called_once_with(f"job:{job_id}")


async def test_stream_cleans_up_on_completion(client: AsyncClient):
    headers = await _register_and_login(client, suffix="cleanup")
    job_id = await _create_job(client, headers)

    parsed_event = json.dumps({"type": "parsed", "title": "SWE", "company": "X"})
    pubsub = _make_mock_pubsub([{"type": "message", "data": parsed_event}])
    mock_redis = _make_mock_redis(pubsub)

    with patch("app.api.v1.reports.aioredis") as mock_mod:
        mock_mod.from_url = AsyncMock(return_value=mock_redis)
        await client.get(
            f"/api/v1/reports/{job_id}/stream",
            headers=headers,
        )

    pubsub.unsubscribe.assert_called_once_with(f"job:{job_id}")
    pubsub.aclose.assert_called_once()
    mock_redis.aclose.assert_called_once()
