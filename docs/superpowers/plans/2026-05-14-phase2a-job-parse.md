# Phase 2A — Job 解析任务 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 POST /api/v1/jobs 创建 Job 并触发 Celery task_parse_jd，异步完成 JD 抓取→LLM 结构化提取→DB 写回→Redis Pub/Sub 发布事件。

**Architecture:** API 层创建 Job（status=parsing）后立即返回；Celery worker 通过 `asyncio.run()` 调用异步帮手函数 `_do_parse_jd`，依次执行 Firecrawl 抓取、LLM 提取、DB 更新，并通过 Redis channel `job:{job_id}` 发布事件。Worker 自行管理 DB session 和 Redis 连接（每次任务创建新连接），与 FastAPI event loop 完全解耦。

**Tech Stack:** FastAPI, SQLAlchemy async, Celery 5.x, `redis.asyncio`, OpenAI gpt-4o-mini（JSON mode）, Firecrawl, Alembic, pytest + pytest-asyncio + unittest.mock

---

## 文件结构

| 操作 | 路径 | 职责 |
|------|------|------|
| Modify | `backend/app/models/job.py` | 新增 user_id FK、resume_id、requirements JSON、jd_summary Text、selected_directions JSON、salary_range、location、work_type |
| Modify | `backend/app/schemas/job.py` | 新增 ExtractedJobInfo（含 salary_range/location/work_type）；更新 JobCreate（+resume_id）、JobResponse |
| Create | `backend/app/repositories/job_repository.py` | Job 表 CRUD：create_job / get_by_id / update_after_parse / update_status |
| Modify | `backend/app/services/llm_service.py` | chat() 支持 **kwargs；新增 extract_job_info(markdown) → ExtractedJobInfo |
| Modify | `backend/app/tasks/research.py` | 新增 task_parse_jd + _do_parse_jd；保留 run_research（留 Phase 2D） |
| Modify | `backend/app/api/v1/jobs.py` | 实现 create_job：JobRepository 写 DB + task_parse_jd.delay |
| Create | `backend/tests/test_job_repository.py` | JobRepository 集成测试（真实 test DB） |
| Create | `backend/tests/test_llm_service.py` | extract_job_info 单元测试（mock OpenAI） |
| Create | `backend/tests/test_task_parse_jd.py` | _do_parse_jd 单元测试（全 mock） |
| Create | `backend/tests/test_jobs_api.py` | POST /jobs API 集成测试（mock Celery task） |
| Run | Alembic migration | autogenerate + upgrade head |

---

### Task 1: 扩展 Job 模型 + Schema

**Files:**
- Modify: `backend/app/models/job.py`
- Modify: `backend/app/schemas/job.py`

- [ ] **Step 1: 更新 Job ORM 模型**

完整替换 `backend/app/models/job.py`：

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id"), nullable=False, index=True
    )
    resume_id: Mapped[str | None] = mapped_column(String, nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    raw_content: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(String(256))
    company: Mapped[str | None] = mapped_column(String(256))
    requirements: Mapped[list | None] = mapped_column(JSON, nullable=True)
    jd_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    salary_range: Mapped[str | None] = mapped_column(String(256), nullable=True)
    location: Mapped[str | None] = mapped_column(String(256), nullable=True)
    work_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    selected_directions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
```

- [ ] **Step 2: 更新 Schema**

完整替换 `backend/app/schemas/job.py`：

```python
from pydantic import BaseModel, HttpUrl


class ExtractedJobInfo(BaseModel):
    title: str
    company: str
    requirements: list[str]
    jd_summary: str
    salary_range: str | None = None
    location: str | None = None
    work_type: str | None = None


class JobCreate(BaseModel):
    url: HttpUrl
    resume_id: str | None = None


class JobResponse(BaseModel):
    id: str
    url: str
    status: str
    title: str | None = None
    company: str | None = None
    salary_range: str | None = None
    location: str | None = None
    work_type: str | None = None

    model_config = {"from_attributes": True}
```

- [ ] **Step 3: 验证 Python 语法**

```bash
cd backend && python -c "from app.models.job import Job; from app.schemas.job import ExtractedJobInfo, JobCreate, JobResponse; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/job.py backend/app/schemas/job.py
git commit -m "feat: Job 模型新增用户/简历关联和 JD 解析字段"
```

---

### Task 2: JobRepository

**Files:**
- Create: `backend/app/repositories/job_repository.py`
- Create: `backend/tests/test_job_repository.py`

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_job_repository.py`：

```python
import pytest
from app.models.user import User
from app.repositories.job_repository import JobRepository


@pytest.fixture
async def user(db):
    u = User(id="u-1", email="t@example.com", username="testuser", password_hash="h")
    db.add(u)
    await db.commit()
    return u


async def test_create_job_returns_job_with_parsing_status(db, user):
    repo = JobRepository(db)
    job = await repo.create_job(url="https://example.com/job", user_id=user.id)
    assert job.id is not None
    assert job.url == "https://example.com/job"
    assert job.status == "parsing"
    assert job.user_id == user.id


async def test_create_job_with_resume_id(db, user):
    repo = JobRepository(db)
    job = await repo.create_job(
        url="https://example.com/job", user_id=user.id, resume_id="r-1"
    )
    assert job.resume_id == "r-1"


async def test_get_by_id_returns_job(db, user):
    repo = JobRepository(db)
    job = await repo.create_job(url="https://example.com/job", user_id=user.id)
    fetched = await repo.get_by_id(job.id)
    assert fetched.id == job.id


async def test_get_by_id_returns_none_for_missing(db):
    repo = JobRepository(db)
    result = await repo.get_by_id("nonexistent-id")
    assert result is None


async def test_update_after_parse_updates_fields(db, user):
    repo = JobRepository(db)
    job = await repo.create_job(url="https://example.com/job", user_id=user.id)
    await repo.update_after_parse(
        job.id,
        raw_content="## JD\n...",
        title="Software Engineer",
        company="Acme",
        requirements=["Python", "FastAPI"],
        jd_summary="A great role.",
    )
    updated = await repo.get_by_id(job.id)
    assert updated.status == "awaiting_confirm"
    assert updated.title == "Software Engineer"
    assert updated.company == "Acme"
    assert updated.requirements == ["Python", "FastAPI"]
    assert updated.jd_summary == "A great role."
    assert updated.raw_content == "## JD\n..."


async def test_update_status(db, user):
    repo = JobRepository(db)
    job = await repo.create_job(url="https://example.com/job", user_id=user.id)
    await repo.update_status(job.id, "failed")
    updated = await repo.get_by_id(job.id)
    assert updated.status == "failed"
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend && python -m pytest tests/test_job_repository.py -v
```

Expected: `ImportError` 或 `ModuleNotFoundError`（JobRepository 不存在）

- [ ] **Step 3: 实现 JobRepository**

新建 `backend/app/repositories/job_repository.py`：

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_job(
        self, url: str, user_id: str, resume_id: str | None = None
    ) -> Job:
        job = Job(url=url, user_id=user_id, resume_id=resume_id, status="parsing")
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def get_by_id(self, job_id: str) -> Job | None:
        result = await self.session.execute(select(Job).where(Job.id == job_id))
        return result.scalar_one_or_none()

    async def update_after_parse(
        self,
        job_id: str,
        *,
        raw_content: str,
        title: str,
        company: str,
        requirements: list[str],
        jd_summary: str,
        salary_range: str | None = None,
        location: str | None = None,
        work_type: str | None = None,
    ) -> None:
        job = await self.get_by_id(job_id)
        if not job:
            return
        job.raw_content = raw_content
        job.title = title
        job.company = company
        job.requirements = requirements
        job.jd_summary = jd_summary
        job.salary_range = salary_range
        job.location = location
        job.work_type = work_type
        job.status = "awaiting_confirm"
        await self.session.commit()

    async def update_status(self, job_id: str, status: str) -> None:
        job = await self.get_by_id(job_id)
        if not job:
            return
        job.status = status
        await self.session.commit()
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd backend && python -m pytest tests/test_job_repository.py -v
```

Expected: 6 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/job_repository.py backend/tests/test_job_repository.py
git commit -m "feat: 新增 JobRepository — Job 表 CRUD 数据访问层"
```

---

### Task 3: LLMService.extract_job_info

**Files:**
- Modify: `backend/app/services/llm_service.py`
- Create: `backend/tests/test_llm_service.py`

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_llm_service.py`：

```python
import json
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.job import ExtractedJobInfo
from app.services.llm_service import extract_job_info


async def test_extract_job_info_returns_structured_info():
    sample_response = json.dumps({
        "title": "Senior Python Developer",
        "company": "TechCorp",
        "requirements": ["Python 3.10+", "FastAPI", "PostgreSQL"],
        "jd_summary": "We are looking for a Python developer to join our backend team.",
    })

    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = sample_response

    with patch("app.services.llm_service._get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)
        mock_get_client.return_value = mock_client

        result = await extract_job_info("## Senior Python Developer\nTechCorp is hiring...")

    assert isinstance(result, ExtractedJobInfo)
    assert result.title == "Senior Python Developer"
    assert result.company == "TechCorp"
    assert result.requirements == ["Python 3.10+", "FastAPI", "PostgreSQL"]
    assert "Python developer" in result.jd_summary


async def test_extract_job_info_uses_gpt4o_mini_with_json_mode():
    sample_response = json.dumps({
        "title": "Engineer",
        "company": "Co",
        "requirements": ["Python"],
        "jd_summary": "A role.",
    })

    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = sample_response

    with patch("app.services.llm_service._get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)
        mock_get_client.return_value = mock_client

        await extract_job_info("## Job\nSome description")

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "gpt-4o-mini"
        assert call_kwargs["response_format"] == {"type": "json_object"}
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend && python -m pytest tests/test_llm_service.py -v
```

Expected: `ImportError`（extract_job_info 不存在）

- [ ] **Step 3: 更新 llm_service.py**

完整替换 `backend/app/services/llm_service.py`：

```python
import json

from openai import AsyncOpenAI

from app.core.config import settings
from app.schemas.job import ExtractedJobInfo

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


async def chat(messages: list[dict], model: str = "gpt-4o", **kwargs) -> str:
    client = _get_client()
    response = await client.chat.completions.create(
        model=model, messages=messages, **kwargs
    )
    return response.choices[0].message.content


async def extract_job_info(markdown: str) -> ExtractedJobInfo:
    system_prompt = (
        "You are a job description parser. Extract key information from the job description "
        "and return a JSON object with these exact fields:\n"
        '- "title": string (job title)\n'
        '- "company": string (company name)\n'
        '- "requirements": array of strings (key requirements, max 10 items)\n'
        '- "jd_summary": string (2-3 sentence summary of the role)\n'
        '- "salary_range": string or null (e.g. "15k-25k", "年薪30万", "$80K-120K"; null if not mentioned)\n'
        '- "location": string or null (city/region, e.g. "北京", "Remote", "Shanghai"; null if not mentioned)\n'
        '- "work_type": string or null ("remote", "hybrid", or "onsite"; null if not mentioned)\n'
        "Return only valid JSON, no markdown."
    )
    response_text = await chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": markdown},
        ],
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
    )
    data = json.loads(response_text)
    return ExtractedJobInfo(**data)
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd backend && python -m pytest tests/test_llm_service.py -v
```

Expected: 2 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/llm_service.py backend/tests/test_llm_service.py
git commit -m "feat: LLMService 新增 extract_job_info — 从 JD Markdown 提取结构化字段"
```

---

### Task 4: task_parse_jd Celery Task

**Files:**
- Modify: `backend/app/tasks/research.py`
- Create: `backend/tests/test_task_parse_jd.py`

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_task_parse_jd.py`：

```python
import json
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.job import ExtractedJobInfo


async def test_do_parse_jd_updates_db_and_publishes_event():
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
    )

    with (
        patch("app.tasks.research.AsyncSessionLocal", return_value=mock_session_ctx),
        patch("app.tasks.research.JobRepository", return_value=mock_repo),
        patch("app.tasks.research.scrape_url", AsyncMock(return_value="## Job\n...")),
        patch("app.tasks.research.extract_job_info", AsyncMock(return_value=mock_info)),
        patch("app.tasks.research.aioredis") as mock_aioredis_mod,
    ):
        mock_aioredis_mod.from_url = AsyncMock(return_value=mock_redis)

        from app.tasks.research import _do_parse_jd
        await _do_parse_jd("j-1")

    mock_repo.update_after_parse.assert_called_once_with(
        "j-1",
        raw_content="## Job\n...",
        title="SWE",
        company="Acme",
        requirements=["Python", "FastAPI"],
        jd_summary="A great role at Acme.",
        salary_range=None,
        location=None,
        work_type=None,
    )
    mock_redis.publish.assert_called_once()
    channel, payload_str = mock_redis.publish.call_args[0]
    assert channel == "job:j-1"
    payload = json.loads(payload_str)
    assert payload["type"] == "parsed"
    assert payload["title"] == "SWE"
    assert payload["company"] == "Acme"
    mock_redis.aclose.assert_called_once()


async def test_do_parse_jd_publishes_error_on_exception():
    mock_repo = AsyncMock()
    mock_repo.get_by_id.return_value = MagicMock(
        id="j-1", url="https://example.com/job"
    )

    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=MagicMock())
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_redis = AsyncMock()

    with (
        patch("app.tasks.research.AsyncSessionLocal", return_value=mock_session_ctx),
        patch("app.tasks.research.JobRepository", return_value=mock_repo),
        patch(
            "app.tasks.research.scrape_url",
            AsyncMock(side_effect=RuntimeError("Network error")),
        ),
        patch("app.tasks.research.aioredis") as mock_aioredis_mod,
    ):
        mock_aioredis_mod.from_url = AsyncMock(return_value=mock_redis)

        from app.tasks.research import _do_parse_jd
        await _do_parse_jd("j-1")

    mock_repo.update_status.assert_called_once_with("j-1", "failed")
    mock_redis.publish.assert_called()
    channel, payload_str = mock_redis.publish.call_args[0]
    assert channel == "job:j-1"
    payload = json.loads(payload_str)
    assert payload["type"] == "error"
    mock_redis.aclose.assert_called_once()
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend && python -m pytest tests/test_task_parse_jd.py -v
```

Expected: `ImportError`（`_do_parse_jd` 不存在）

- [ ] **Step 3: 实现 task_parse_jd**

完整替换 `backend/app/tasks/research.py`：

```python
import asyncio
import json

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.repositories.job_repository import JobRepository
from app.services.crawler_service import scrape_url
from app.services.llm_service import extract_job_info
from app.tasks import celery_app


@celery_app.task(name="research.parse_jd", soft_time_limit=120)
def task_parse_jd(job_id: str) -> None:
    asyncio.run(_do_parse_jd(job_id))


async def _do_parse_jd(job_id: str) -> None:
    redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        async with AsyncSessionLocal() as session:
            repo = JobRepository(session)
            job = await repo.get_by_id(job_id)
            if not job:
                return

            raw_content = await scrape_url(job.url)
            info = await extract_job_info(raw_content)

            await repo.update_after_parse(
                job_id,
                raw_content=raw_content,
                title=info.title,
                company=info.company,
                requirements=info.requirements,
                jd_summary=info.jd_summary,
                salary_range=info.salary_range,
                location=info.location,
                work_type=info.work_type,
            )

        await redis.publish(
            f"job:{job_id}",
            json.dumps({
                "type": "parsed",
                "title": info.title,
                "company": info.company,
                "requirements": info.requirements,
                "salary_range": info.salary_range,
                "location": info.location,
                "work_type": info.work_type,
            }),
        )
    except Exception:
        async with AsyncSessionLocal() as session:
            repo = JobRepository(session)
            await repo.update_status(job_id, "failed")
        await redis.publish(
            f"job:{job_id}",
            json.dumps({"type": "error", "job_id": job_id}),
        )
    finally:
        await redis.aclose()


@celery_app.task(name="research.run", soft_time_limit=300)
def run_research(job_id: str, resume_id: str | None = None) -> None:
    # TODO: Phase 2D — LangGraph 研究图
    raise NotImplementedError
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd backend && python -m pytest tests/test_task_parse_jd.py -v
```

Expected: 2 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/tasks/research.py backend/tests/test_task_parse_jd.py
git commit -m "feat: 新增 task_parse_jd — Celery 异步 JD 抓取 + LLM 解析 + Redis 事件发布"
```

---

### Task 5: POST /api/v1/jobs 实现

**Files:**
- Modify: `backend/app/api/v1/jobs.py`
- Create: `backend/tests/test_jobs_api.py`

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_jobs_api.py`：

```python
from unittest.mock import patch

from httpx import AsyncClient


async def _get_auth_headers(client: AsyncClient) -> dict:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "jobtest@example.com", "username": "jobtest", "password": "password123"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "jobtest@example.com", "password": "password123"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_create_job_returns_201_with_parsing_status(client):
    headers = await _get_auth_headers(client)

    with patch("app.api.v1.jobs.task_parse_jd") as mock_task:
        mock_task.delay = lambda job_id: None

        resp = await client.post(
            "/api/v1/jobs/",
            json={"url": "https://example.com/job"},
            headers=headers,
        )

    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["status"] == "parsing"
    assert data["url"] == "https://example.com/job"


async def test_create_job_triggers_celery_task(client):
    headers = await _get_auth_headers(client)
    called_with = []

    with patch("app.api.v1.jobs.task_parse_jd") as mock_task:
        mock_task.delay = lambda job_id: called_with.append(job_id)

        resp = await client.post(
            "/api/v1/jobs/",
            json={"url": "https://example.com/job2"},
            headers=headers,
        )

    assert resp.status_code == 201
    job_id = resp.json()["id"]
    assert job_id in called_with


async def test_create_job_requires_auth(client):
    resp = await client.post(
        "/api/v1/jobs/",
        json={"url": "https://example.com/job"},
    )
    assert resp.status_code == 401


async def test_create_job_rejects_invalid_url(client):
    headers = await _get_auth_headers(client)

    with patch("app.api.v1.jobs.task_parse_jd") as mock_task:
        mock_task.delay = lambda job_id: None

        resp = await client.post(
            "/api/v1/jobs/",
            json={"url": "not-a-valid-url"},
            headers=headers,
        )

    assert resp.status_code == 422
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend && python -m pytest tests/test_jobs_api.py -v
```

Expected: `NotImplementedError`（create_job 尚未实现）

- [ ] **Step 3: 实现 create_job**

完整替换 `backend/app/api/v1/jobs.py`：

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.repositories.job_repository import JobRepository
from app.schemas.job import JobCreate, JobResponse
from app.services.auth_service import get_current_user
from app.tasks.research import task_parse_jd

router = APIRouter()


@router.post("/", response_model=JobResponse, status_code=201)
async def create_job(
    payload: JobCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = JobRepository(db)
    job = await repo.create_job(
        url=str(payload.url),
        user_id=current_user.id,
        resume_id=payload.resume_id,
    )
    task_parse_jd.delay(job.id)
    return job
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd backend && python -m pytest tests/test_jobs_api.py -v
```

Expected: 4 tests PASSED

- [ ] **Step 5: 运行全量测试，确认无回归**

```bash
cd backend && python -m pytest -v
```

Expected: 全部 PASSED（auth + job 测试）

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/jobs.py backend/tests/test_jobs_api.py
git commit -m "feat: 实现 POST /api/v1/jobs — 创建 Job 并触发 task_parse_jd"
```

---

### Task 6: Alembic 迁移

**Files:**
- Run: Alembic autogenerate + upgrade head

- [ ] **Step 1: 生成迁移文件**

```bash
cd backend && alembic revision --autogenerate -m "add job fields user_id resume_id requirements jd_summary selected_directions"
```

Expected: 输出 `Generating .../versions/xxxx_add_job_fields_....py`

- [ ] **Step 2: Review 迁移文件内容**

打开 `backend/alembic/versions/` 下最新文件，确认包含：
- `user_id` 列（VARCHAR，NOT NULL，FK to users.id）
- `resume_id` 列（VARCHAR，nullable）
- `requirements` 列（JSON，nullable）
- `jd_summary` 列（TEXT，nullable）
- `selected_directions` 列（JSON，nullable）
- 外键约束 `fk_jobs_user_id_users`（或类似名称）

- [ ] **Step 3: 应用迁移**

```bash
cd backend && alembic upgrade head
```

Expected: 无报错，输出 `Running upgrade ... -> xxxx`

- [ ] **Step 4: 验证表结构**

```bash
cd backend && python -c "
import asyncio
from sqlalchemy import text
from app.core.database import engine

async def check():
    async with engine.connect() as conn:
        result = await conn.execute(
            text(\"SELECT column_name FROM information_schema.columns WHERE table_name='jobs' ORDER BY ordinal_position\")
        )
        cols = [r[0] for r in result.fetchall()]
        print('Jobs columns:', cols)
        for c in ['user_id', 'resume_id', 'requirements', 'jd_summary', 'selected_directions']:
            assert c in cols, f'Missing column: {c}'
        print('All new columns present!')

asyncio.run(check())
"
```

Expected: `All new columns present!`

- [ ] **Step 5: Commit（含迁移文件）**

```bash
git add backend/alembic/versions/
git commit -m "feat: Alembic 迁移 — Job 表新增用户关联和 JD 解析字段"
```

---

## 自我审查

**Spec 覆盖检查：**
- ✅ `POST /api/v1/jobs (url, resume_id?)` → Task 5
- ✅ 创建 Job（status=parsing）→ Task 2（create_job）
- ✅ 触发 Celery task_parse_jd.delay(job_id) → Task 5（create_job）
- ✅ 返回 `{ id, status: "parsing" }` → Task 5（JobResponse）
- ✅ scrape_url(job.url) [Firecrawl] → Task 4（_do_parse_jd）
- ✅ LLM 提取 title, company, requirements, summary → Task 3（extract_job_info）
- ✅ 更新 Job（raw_content, title, company, status="awaiting_confirm"）→ Task 2（update_after_parse）
- ✅ Redis Pub/Sub publish event → Task 4（_do_parse_jd）
- ✅ Job 模型新增字段（user_id, resume_id, requirements, jd_summary, selected_directions）→ Task 1
- ✅ Alembic 迁移 → Task 6

**类型一致性：**
- `ExtractedJobInfo` 在 Task 1（schemas/job.py）定义，Task 3（llm_service.py）返回，Task 4（_do_parse_jd）通过 `info.title` 等访问 → 一致
- `JobRepository.update_after_parse(job_id, *, raw_content, title, company, requirements, jd_summary)` 在 Task 2 定义，Task 4 调用签名完全一致
- `task_parse_jd.delay(job.id)` 在 Task 4 定义，Task 5 调用一致
