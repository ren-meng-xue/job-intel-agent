import json
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.job import ExtractedJobInfo
from app.tasks import celery_app
from app.tasks.research import _do_parse_jd


async def test_do_parse_jd_updates_db_and_publishes_event():
    """正常流程：抓取 → LLM 提取 → 写库 → Redis publish parsed"""
    mock_job = MagicMock(id="j-1", url="https://example.com/job")
    mock_repo = AsyncMock()
    mock_repo.get_by_id.return_value = mock_job

    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=MagicMock())
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_redis = AsyncMock()
    mock_info = ExtractedJobInfo(
        title="SWE",
        company="Acme",
        requirements=["Python", "FastAPI"],
        jd_summary="A great role at Acme.",
        salary_range="25k-40k",
        location="上海",
        work_type="hybrid",
    )

    with (
        patch("app.tasks.research.AsyncSessionLocal", return_value=mock_session_ctx),
        patch("app.tasks.research.JobRepository", return_value=mock_repo),
        patch("app.tasks.research.scrape_url", AsyncMock(return_value="## Job\n...")),
        patch("app.tasks.research.extract_job_info", AsyncMock(return_value=mock_info)),
        patch("app.tasks.research.aioredis") as mock_aioredis_mod,
    ):
        mock_aioredis_mod.from_url = AsyncMock(return_value=mock_redis)
        await _do_parse_jd("j-1")

    # 验证写库调用参数正确
    mock_repo.update_after_parse.assert_called_once_with(
        "j-1",
        raw_content="## Job\n...",
        title="SWE",
        company="Acme",
        requirements=["Python", "FastAPI"],
        jd_summary="A great role at Acme.",
        salary_range="25k-40k",
        location="上海",
        work_type="hybrid",
    )

    # 验证 Redis 事件内容
    mock_redis.publish.assert_called_once()
    channel, payload_str = mock_redis.publish.call_args[0]
    assert channel == "job:j-1"
    payload = json.loads(payload_str)
    assert payload["type"] == "parsed"
    assert payload["step"] == "parse_complete"
    assert payload["message"] == "JD 解析完成，请确认职位信息"
    assert payload["title"] == "SWE"
    assert payload["salary_range"] == "25k-40k"
    assert payload["location"] == "上海"
    mock_redis.aclose.assert_called_once()


def test_celery_registers_app_tasks():
    """worker 通过 app.tasks:celery_app 启动时应能发现所有任务"""
    assert "research.parse_jd" in celery_app.tasks
    assert "research.run" in celery_app.tasks
    assert "resume.parse" in celery_app.tasks


async def test_do_parse_jd_publishes_error_on_exception():
    """抓取失败时：status → failed，publish error 事件"""
    mock_repo = AsyncMock()
    mock_repo.get_by_id.return_value = MagicMock(id="j-1", url="https://example.com/job")

    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=MagicMock())
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_redis = AsyncMock()

    with (
        patch("app.tasks.research.AsyncSessionLocal", return_value=mock_session_ctx),
        patch("app.tasks.research.JobRepository", return_value=mock_repo),
        patch("app.tasks.research.scrape_url", AsyncMock(side_effect=RuntimeError("Network error"))),
        patch("app.tasks.research.aioredis") as mock_aioredis_mod,
    ):
        mock_aioredis_mod.from_url = AsyncMock(return_value=mock_redis)
        await _do_parse_jd("j-1")

    mock_repo.update_status.assert_called_once_with("j-1", "failed")
    channel, payload_str = mock_redis.publish.call_args[0]
    assert channel == "job:j-1"
    assert json.loads(payload_str)["type"] == "error"
    mock_redis.aclose.assert_called_once()


async def test_do_parse_jd_returns_early_if_job_not_found():
    """job_id 不存在时直接返回，不抛异常"""
    mock_repo = AsyncMock()
    mock_repo.get_by_id.return_value = None

    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=MagicMock())
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_redis = AsyncMock()

    with (
        patch("app.tasks.research.AsyncSessionLocal", return_value=mock_session_ctx),
        patch("app.tasks.research.JobRepository", return_value=mock_repo),
        patch("app.tasks.research.aioredis") as mock_aioredis_mod,
    ):
        mock_aioredis_mod.from_url = AsyncMock(return_value=mock_redis)
        await _do_parse_jd("nonexistent")

    mock_repo.update_after_parse.assert_not_called()
    mock_redis.publish.assert_not_called()
