# Phase 2E — 简历上传与解析 实施计划

**Goal:** 实现简历上传、文本提取、LLM 结构化解析全链路。用户上传 PDF/DOCX，系统提取文本后通过 Celery 异步调用 LLM 提炼技能、工作经历、教育背景等字段，结果以 SSE 推送 `parsed` 事件通知前端。解析完的简历可关联到 Job（`resume_id` 字段），为后续 JD-简历匹配打基础。

**简历数量约束：每个用户只能保存一份简历。** 上传前检查是否已有记录，有则返回 409。用户需先删除旧简历再重新上传。不自动清理——后续可直接复用于多个 Job。

**可并行于 Phase 2D：** 2E 完全独立于 LangGraph 研究图，仅共用 `llm_service.py` 和 Redis Pub/Sub 模式。

**Tech Stack:** FastAPI · pdfplumber · python-docx · SQLAlchemy async · Celery · Redis Pub/Sub (SSE) · OpenAI gpt-4o-mini · Python 3.12

---

## 状态机

```
POST /resume/ 上传文件
       │
       ▼
   提取文本（同步，pdfplumber / python-docx）
       │
       ▼ dispatch Celery task
   pending → parsing → done
                  │
                  └──→ failed（LLM 调用失败或文本为空）
```

---

## 文件结构

| 操作 | 路径 | 职责 |
|------|------|------|
| Create | `backend/app/models/resume.py` | Resume ORM 模型 |
| Create | `backend/alembic/versions/xxxx_create_resumes_table.py` | `alembic revision --autogenerate` 生成 |
| Create | `backend/app/repositories/resume_repository.py` | Resume CRUD |
| Create | `backend/app/schemas/resume.py` | Pydantic Schemas |
| Modify | `backend/app/services/resume_service.py` | pdfplumber / python-docx 文本提取 |
| Modify | `backend/app/services/llm_service.py` | 新增 `extract_resume_info` |
| Create | `backend/app/tasks/resume.py` | Celery `task_parse_resume` |
| Modify | `backend/app/api/v1/resume.py` | 实现上传 / 列表 / 详情 / SSE / 删除 |
| Modify | `backend/pyproject.toml` | 新增 pdfplumber、python-docx 依赖 |
| Create | `backend/tests/test_resume_parse.py` | 解析逻辑单元测试 |
| Create | `backend/tests/test_resume_api.py` | 端点集成测试 |

---

## Task 1 — Resume ORM 模型

**文件：** `backend/app/models/resume.py`

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    raw_content: Mapped[str | None] = mapped_column(Text)        # 提取的纯文本
    skills: Mapped[list | None] = mapped_column(JSON)            # ["Python", "React", ...]
    experience_years: Mapped[int | None] = mapped_column(Integer)
    work_experience: Mapped[list | None] = mapped_column(JSON)   # [{company, title, duration, description}]
    education: Mapped[list | None] = mapped_column(JSON)         # [{school, degree, major, year}]
    summary: Mapped[str | None] = mapped_column(Text)            # LLM 生成的职业摘要
    parsing_error: Mapped[str | None] = mapped_column(Text)      # 失败原因
    # pending → parsing → done / failed
    status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
```

运行迁移：
```bash
cd backend && alembic revision --autogenerate -m "create_resumes_table" && alembic upgrade head
```

---

## Task 2 — ResumeRepository

**文件：** `backend/app/repositories/resume_repository.py`

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resume import Resume


class ResumeRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, resume: Resume) -> Resume:
        self.session.add(resume)
        await self.session.commit()
        await self.session.refresh(resume)
        return resume

    async def get_by_id(self, resume_id: str) -> Resume | None:
        result = await self.session.execute(
            select(Resume).where(Resume.id == resume_id)
        )
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: str) -> list[Resume]:
        result = await self.session.execute(
            select(Resume).where(Resume.user_id == user_id).order_by(Resume.created_at.desc())
        )
        return list(result.scalars().all())

    async def update(self, resume_id: str, fields: dict) -> None:
        result = await self.session.execute(
            select(Resume).where(Resume.id == resume_id)
        )
        resume = result.scalar_one_or_none()
        if resume:
            for k, v in fields.items():
                setattr(resume, k, v)
            await self.session.commit()

    async def delete(self, resume_id: str) -> bool:
        result = await self.session.execute(
            select(Resume).where(Resume.id == resume_id)
        )
        resume = result.scalar_one_or_none()
        if not resume:
            return False
        await self.session.delete(resume)
        await self.session.commit()
        return True
```

---

## Task 3 — Pydantic Schemas

**文件：** `backend/app/schemas/resume.py`

```python
from datetime import datetime
from pydantic import BaseModel


class ResumeResponse(BaseModel):
    id: str
    filename: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ResumeDetailResponse(BaseModel):
    id: str
    filename: str
    status: str
    skills: list | None = None
    experience_years: int | None = None
    work_experience: list | None = None
    education: list | None = None
    summary: str | None = None
    parsing_error: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
```

---

## Task 4 — 文本提取（resume_service.py）

**文件：** `backend/app/services/resume_service.py`

支持 PDF（pdfplumber）和 DOCX（python-docx），其他格式抛 `ValueError`。
扫描版 PDF（提取文本为空）记录 `parsing_error`，不阻塞流程。

```python
import io


def extract_text(file_bytes: bytes, filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return _extract_pdf(file_bytes)
    if lower.endswith(".docx"):
        return _extract_docx(file_bytes)
    raise ValueError(f"不支持的文件格式：{filename}")


def _extract_pdf(file_bytes: bytes) -> str:
    import pdfplumber
    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    return "\n".join(text_parts).strip()


def _extract_docx(file_bytes: bytes) -> str:
    from docx import Document
    doc = Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
```

---

## Task 5 — LLM extract_resume_info

**文件：** `backend/app/services/llm_service.py`（新增函数）

```python
async def extract_resume_info(raw_content: str) -> dict:
    """从简历文本提取结构化字段，返回 dict（对应 Resume 模型字段）"""
    system_prompt = (
        "你是简历解析专家。从下面的简历文本中提取关键信息，"
        "以 JSON 格式返回，字段：\n"
        "- skills: list[str]，技术/专业技能列表\n"
        "- experience_years: int，估算总工作年限（在校/实习不计），无法判断填 null\n"
        "- work_experience: list[{company, title, duration, description}]\n"
        "- education: list[{school, degree, major, year}]\n"
        "- summary: str，2-3 句职业摘要（中文）\n"
        "信息不足的字段填 null，不要编造。"
    )
    resp = await chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": raw_content[:8000]},  # 防超 token
        ],
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
    )
    return json.loads(resp)
```

---

## Task 6 — Celery task_parse_resume

**文件：** `backend/app/tasks/resume.py`

```python
import asyncio
import json

import redis.asyncio as aioredis

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.repositories.resume_repository import ResumeRepository
from app.services.llm_service import extract_resume_info


@celery_app.task(name="resume.parse", soft_time_limit=120)
def task_parse_resume(resume_id: str) -> None:
    asyncio.run(_do_parse_resume(resume_id))


async def _do_parse_resume(resume_id: str) -> None:
    redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    channel = f"resume:{resume_id}"
    try:
        async with AsyncSessionLocal() as session:
            repo = ResumeRepository(session)
            resume = await repo.get_by_id(resume_id)
            if not resume:
                return

        if not resume.raw_content:
            async with AsyncSessionLocal() as session:
                repo = ResumeRepository(session)
                await repo.update(resume_id, {
                    "status": "failed",
                    "parsing_error": "文件文本为空，可能是扫描版 PDF",
                })
            await redis.publish(channel, json.dumps({"type": "error", "resume_id": resume_id}))
            return

        info = await extract_resume_info(resume.raw_content)
        async with AsyncSessionLocal() as session:
            repo = ResumeRepository(session)
            await repo.update(resume_id, {
                "skills": info.get("skills"),
                "experience_years": info.get("experience_years"),
                "work_experience": info.get("work_experience"),
                "education": info.get("education"),
                "summary": info.get("summary"),
                "status": "done",
            })

        await redis.publish(channel, json.dumps({"type": "parsed", "resume_id": resume_id}))

    except Exception as e:
        async with AsyncSessionLocal() as session:
            repo = ResumeRepository(session)
            await repo.update(resume_id, {"status": "failed", "parsing_error": str(e)})
        await redis.publish(channel, json.dumps({"type": "error", "resume_id": resume_id}))
    finally:
        await redis.aclose()
```

---

## Task 7 — API 端点

**文件：** `backend/app/api/v1/resume.py`（全量替换）

```python
import json

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.resume import Resume
from app.models.user import User
from app.repositories.resume_repository import ResumeRepository
from app.schemas.resume import ResumeDetailResponse, ResumeResponse
from app.services.auth_service import get_current_user
from app.services.resume_service import extract_text
from app.tasks.resume import task_parse_resume

router = APIRouter()

_ALLOWED_TYPES = {"application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
_MAX_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/", status_code=202, response_model=ResumeResponse)
async def upload_resume(
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传简历（PDF/DOCX），同步提取文本，异步 LLM 解析"""
    if file.content_type not in _ALLOWED_TYPES:
        raise HTTPException(400, "仅支持 PDF 或 DOCX 格式")

    file_bytes = await file.read()
    if len(file_bytes) > _MAX_SIZE:
        raise HTTPException(413, "文件超过 10 MB 限制")

    try:
        raw_content = extract_text(file_bytes, file.filename or "")
    except ValueError as e:
        raise HTTPException(400, str(e))

    repo = ResumeRepository(db)
    resume = Resume(
        user_id=current_user.id,
        filename=file.filename or "resume",
        raw_content=raw_content or None,
        status="parsing",
    )
    resume = await repo.create(resume)
    task_parse_resume.delay(resume.id)
    return resume


@router.get("/", response_model=list[ResumeResponse])
async def list_resumes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = ResumeRepository(db)
    return await repo.list_by_user(current_user.id)


@router.get("/{resume_id}", response_model=ResumeDetailResponse)
async def get_resume(
    resume_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = ResumeRepository(db)
    resume = await repo.get_by_id(resume_id)
    if not resume:
        raise HTTPException(404, "Resume not found")
    if resume.user_id != current_user.id:
        raise HTTPException(403, "Access denied")
    return resume


@router.get("/{resume_id}/stream")
async def stream_resume(
    resume_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """SSE：订阅简历解析进度，parsed / error 终态后关闭"""
    repo = ResumeRepository(db)
    resume = await repo.get_by_id(resume_id)
    if not resume:
        raise HTTPException(404, "Resume not found")
    if resume.user_id != current_user.id:
        raise HTTPException(403, "Access denied")

    return StreamingResponse(
        _sse_generator(resume_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete("/{resume_id}", status_code=204)
async def delete_resume(
    resume_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = ResumeRepository(db)
    resume = await repo.get_by_id(resume_id)
    if not resume:
        raise HTTPException(404, "Resume not found")
    if resume.user_id != current_user.id:
        raise HTTPException(403, "Access denied")
    await repo.delete(resume_id)


async def _sse_generator(resume_id: str):
    import asyncio
    redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"resume:{resume_id}")
    try:
        while True:
            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True),
                    timeout=15.0,
                )
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
                continue
            if message is None:
                await asyncio.sleep(0.1)
                continue
            data = message.get("data")
            if not isinstance(data, str):
                continue
            yield f"data: {data}\n\n"
            try:
                if json.loads(data).get("type") in ("parsed", "error"):
                    break
            except (json.JSONDecodeError, AttributeError):
                pass
    finally:
        await pubsub.unsubscribe(f"resume:{resume_id}")
        await pubsub.aclose()
        await redis.aclose()
```

---

## Task 8 — pyproject.toml 依赖

```toml
"pdfplumber>=0.11",
"python-docx>=1.1",
```

---

## Task 9 — 测试

**文件：** `backend/tests/test_resume_parse.py`

- PDF 正常文本 → extract_text 返回非空字符串
- DOCX 正常文本 → extract_text 返回非空字符串
- 不支持格式（.txt）→ ValueError
- LLM 返回完整字段 → extract_resume_info 正确解析 JSON

**文件：** `backend/tests/test_resume_api.py`

- 未鉴权 → 401
- 上传 PDF → 202 + status=parsing，Celery task 触发（mock）
- 上传非法格式 → 400
- 文件超限 → 413
- GET /resume/ → 仅返回当前用户的记录
- GET /resume/{id} → 200（本人）/ 403（他人）/ 404（不存在）
- DELETE /resume/{id} → 204（本人）/ 403（他人）
- task_parse_resume 成功路径 → status=done，字段写入 DB，Redis 发布 parsed
- task_parse_resume 空文本 → status=failed，Redis 发布 error

---

## 关键设计决策

1. **文件内容存 DB**：开发阶段 `raw_content` 直接写 TEXT 列，不引入 S3。Phase 3 迁移时替换为 `storage_url`。
2. **同步文本提取 + 异步 LLM**：pdfplumber 提取毫秒级，可在请求内完成；LLM 调用 ~3-5s，走 Celery 避免超时。
3. **扫描版 PDF 优雅降级**：提取文本为空时记录 `parsing_error`，status 置 failed，不引入 OCR 依赖（Phase 3 可加）。
4. **SSE 频道独立**：`resume:{id}` 与 `job:{id}` 互不干扰，前端按 ID 订阅各自进度。
5. **LLM token 截断**：`raw_content[:8000]` 防止超 gpt-4o-mini 上下文，正常简历 1-3 页远不到此限。

---

## 验证清单

- [ ] Resume 模型 + Alembic 迁移成功执行
- [ ] 上传 PDF → 202，status=parsing
- [ ] 上传 DOCX → 202，status=parsing
- [ ] 上传非 PDF/DOCX → 400
- [ ] SSE 流收到 `parsed` 事件 → status=done，字段非空
- [ ] SSE 流收到 `error` 事件 → status=failed，parsing_error 有内容
- [ ] GET /resume/ 只返回当前用户数据
- [ ] 跨用户访问 → 403
- [ ] DELETE → 204，DB 记录删除
- [ ] Job 创建时可传 resume_id，关联到已解析简历
