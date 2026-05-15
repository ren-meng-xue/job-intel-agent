# Phase 2C — HiTL 确认接口 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 HiTL（Human-in-the-Loop）入口阶段——`awaiting_confirm` 用户审核/修正 LLM 提取的 JD 字段（不满意可 reparse 重来），`awaiting_directions` LLM 自动建议调研方向、用户勾选或换一批，最终提交方向触发 Phase 2D 研究。

**Architecture:** API 层（FastAPI）→ Repository 层（SQLAlchemy async）→ Celery task。每个等待阶段「直接编辑」+「带 feedback 重来」双通道共存。

**Tech Stack:** FastAPI · SQLAlchemy async · Pydantic v2 · Celery · Python 3.12

---

## 文件结构

| 文件 | 操作 | 说明 |
|---|---|---|
| `backend/app/schemas/job.py` | 修改 | 新增 `JobConfirmPayload`、`JobStartPayload`、`JobDetailResponse`、`DirectionsResponse`、`DirectionsPayload`、`ReparsePayload` |
| `backend/app/repositories/job_repository.py` | 修改 | 新增 `confirm_job`、`start_research` 方法 |
| `backend/app/services/llm_service.py` | 修改 | 新增 `suggest_directions`：LLM 根据 JD 自动建议调研方向 |
| `backend/app/api/v1/jobs.py` | 修改 | 新增 `POST /confirm`、`POST /reparse`、`POST /directions`、`POST /start` |
| `backend/app/tasks/research.py` | 修改 | `task_parse_jd` 支持 feedback 参数注入 prompt；`task_run_research` 重命名 |

---

## Task 1 — 新增 Schema

**文件：** `backend/app/schemas/job.py`

**说明：**
- `JobConfirmPayload`：用户修正字段，全部可选，只传需要改的
- `JobStartPayload`：用户提交调研方向列表
- `JobDetailResponse`：返回完整 JD 信息（比 `JobResponse` 多 requirements / jd_summary / selected_directions）

- [ ] 打开 `backend/app/schemas/job.py`，将整个文件替换为如下内容：

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


class JobDetailResponse(BaseModel):
    """确认/启动接口返回的完整 Job 信息"""

    id: str
    url: str
    status: str
    title: str | None = None
    company: str | None = None
    requirements: list[str] | None = None
    jd_summary: str | None = None
    salary_range: str | None = None
    location: str | None = None
    work_type: str | None = None
    selected_directions: list[str] | None = None

    model_config = {"from_attributes": True}


class JobConfirmPayload(BaseModel):
    """用户确认/修正 LLM 提取的 JD 字段，全部可选，只传需要覆盖的字段"""

    title: str | None = None
    company: str | None = None
    requirements: list[str] | None = None
    jd_summary: str | None = None
    salary_range: str | None = None
    location: str | None = None
    work_type: str | None = None


class JobStartPayload(BaseModel):
    """用户提交调研方向，触发研究任务"""

    selected_directions: list[str]
```

---

## Task 2 — JobRepository 新增方法

**文件：** `backend/app/repositories/job_repository.py`

**说明：**
- `confirm_job`：只更新用户实际传入（非 None）的字段，status 改为 `awaiting_directions`
- `start_research`：写入 `selected_directions`，status 改为 `researching`
- 两个方法都在操作后调用 `refresh`，返回最新 Job 对象供 API 层序列化

- [ ] 在 `backend/app/repositories/job_repository.py` 的 `update_status` 方法后追加以下两个方法：

```python
    async def confirm_job(
        self,
        job_id: str,
        *,
        title: str | None = None,
        company: str | None = None,
        requirements: list[str] | None = None,
        jd_summary: str | None = None,
        salary_range: str | None = None,
        location: str | None = None,
        work_type: str | None = None,
    ) -> Job | None:
        """用户确认并选择性修正 LLM 提取的字段，status 改为 awaiting_directions。
        只更新调用方显式传入（非 None）的字段，未传字段保持原值。"""
        job = await self.get_by_id(job_id)
        if not job:
            return None
        if title is not None:
            job.title = title
        if company is not None:
            job.company = company
        if requirements is not None:
            job.requirements = requirements
        if jd_summary is not None:
            job.jd_summary = jd_summary
        if salary_range is not None:
            job.salary_range = salary_range
        if location is not None:
            job.location = location
        if work_type is not None:
            job.work_type = work_type
        job.status = "awaiting_directions"
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def start_research(
        self, job_id: str, selected_directions: list[str]
    ) -> Job | None:
        """写入用户选择的调研方向，status 改为 researching，供 Celery task 消费。"""
        job = await self.get_by_id(job_id)
        if not job:
            return None
        job.selected_directions = selected_directions
        job.status = "researching"
        await self.session.commit()
        await self.session.refresh(job)
        return job
```

---

## Task 3 — 实现 POST /jobs/{id}/confirm 端点

**文件：** `backend/app/api/v1/jobs.py`

**说明：**
- 路径 `POST /api/v1/jobs/{job_id}/confirm`
- 鉴权：`get_current_user`
- 权限校验：job.user_id 必须等于 current_user.id，否则 403
- 状态校验：job.status 必须为 `awaiting_confirm`，否则 409 Conflict
- 把 payload 中非 None 的字段传给 `repo.confirm_job`
- 返回 `JobDetailResponse`

- [ ] 将 `backend/app/api/v1/jobs.py` 整个文件替换为以下内容（保留原有 create_job，补充新端点）：

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.repositories.job_repository import JobRepository
from app.schemas.job import (
    JobConfirmPayload,
    JobCreate,
    JobDetailResponse,
    JobResponse,
    JobStartPayload,
)
from app.services.auth_service import get_current_user
from app.tasks.research import task_parse_jd, task_run_research

router = APIRouter()


@router.post("/", response_model=JobResponse, status_code=201)
async def create_job(
    payload: JobCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建 Job 记录并触发异步解析任务，立即返回 status=parsing"""
    repo = JobRepository(db)
    job = await repo.create_job(
        url=str(payload.url),
        user_id=current_user.id,
        resume_id=payload.resume_id,
    )
    task_parse_jd.delay(job.id)
    return job


@router.post("/{job_id}/confirm", response_model=JobDetailResponse)
async def confirm_job(
    job_id: str,
    payload: JobConfirmPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """用户确认并可选修正 LLM 提取的 JD 字段，status 推进到 awaiting_directions。

    - 只传需要覆盖的字段，未传字段保持 LLM 提取结果不变。
    - 要求 job 处于 awaiting_confirm 状态，否则返回 409。
    - 要求 job 属于当前用户，否则返回 403。
    """
    repo = JobRepository(db)
    job = await repo.get_by_id(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job 不存在",
        )
    if job.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权操作该 Job",
        )
    if job.status != "awaiting_confirm":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job 当前状态为 {job.status!r}，须处于 awaiting_confirm 才能确认",
        )

    updated_job = await repo.confirm_job(
        job_id,
        title=payload.title,
        company=payload.company,
        requirements=payload.requirements,
        jd_summary=payload.jd_summary,
        salary_range=payload.salary_range,
        location=payload.location,
        work_type=payload.work_type,
    )
    return updated_job


@router.post("/{job_id}/start", response_model=JobDetailResponse)
async def start_job(
    job_id: str,
    payload: JobStartPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """用户提交调研方向，status 推进到 researching 并触发 Celery 研究任务（Phase 2D）。

    - selected_directions 不可为空列表。
    - 要求 job 处于 awaiting_directions 状态，否则返回 409。
    - 要求 job 属于当前用户，否则返回 403。
    """
    if not payload.selected_directions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="selected_directions 不能为空",
        )

    repo = JobRepository(db)
    job = await repo.get_by_id(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job 不存在",
        )
    if job.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权操作该 Job",
        )
    if job.status != "awaiting_directions":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job 当前状态为 {job.status!r}，须处于 awaiting_directions 才能启动研究",
        )

    updated_job = await repo.start_research(job_id, payload.selected_directions)
    # Phase 2D 实现内部逻辑，此处只负责触发
    task_run_research.delay(job_id)
    return updated_job
```

---

## Task 4 — research.py 补充 task_run_research 占位导出

**文件：** `backend/app/tasks/research.py`

**说明：**
- `run_research` 已存在，但对外名称是 `run_research`，而 `jobs.py` 导入的是 `task_run_research`。
- 需要将现有任务函数重命名为 `task_run_research`（或添加别名），保持命名风格与 `task_parse_jd` 一致。
- 内部逻辑仍是 `raise NotImplementedError`，Phase 2D 再实现。

- [ ] 在 `backend/app/tasks/research.py` 中，将 `run_research` 函数重命名为 `task_run_research`，并更新 Celery task name 保持一致：

```python
@celery_app.task(name="research.run_research", soft_time_limit=300)
def task_run_research(job_id: str, resume_id: str | None = None) -> None:
    """Phase 2D — LangGraph 研究图（待实现）"""
    # TODO: Phase 2D 实现 LangGraph 多步调研 Agent
    raise NotImplementedError
```

将原有的：
```python
@celery_app.task(name="research.run", soft_time_limit=300)
def run_research(job_id: str, resume_id: str | None = None) -> None:
    # TODO: Phase 2D — LangGraph 研究图
    raise NotImplementedError
```
替换为上面的 `task_run_research` 版本。

---

## 关键逻辑说明

### 状态机流转

```
                              ┌─ POST /reparse + feedback ──┐
                              │  status → parsing，重新提取    │
                              │                              │
pending → parsing → awaiting_confirm ──→ awaiting_directions
                         │                      │
              POST /confirm              ┌──────┴──────┐
             （直接编辑字段）              │             │
              status → awaiting_          POST /dir     POST /start
              directions                 + feedback    {selected_directions}
                                         换一批建议      status → researching
                                         原地刷新              │
                                                      Phase 2D 接管
```

### 用户操作模型

| 阶段 | 直接编辑 | 带反馈重来 |
|---|---|---|
| `awaiting_confirm` | POST /confirm 修改字段 | POST /reparse + feedback |
| `awaiting_directions` | 不需要（勾选即可） | POST /directions + feedback 换一批建议 |

### 权限校验模式（两个端点一致）

```
get_job → 404 if not found
       → 403 if job.user_id != current_user.id
       → 409 if job.status != expected_status
       → 执行业务逻辑
```

### confirm_job 的字段更新策略

`confirm_job` 只更新调用方传入**非 None** 的字段，用户未传的字段保留 LLM 提取结果。这允许前端只发送有修改的字段，无需传递完整 payload。

### task_run_research 调用时机

`start_research` 写库成功后立即调用 `.delay(job_id)`，此时 job.status 已为 `researching`，Celery worker 可通过 `get_by_id` 拿到完整信息（含 `selected_directions`）开始研究。

---

## 验证清单

- [ ] `POST /jobs/{id}/confirm`：job 不存在返回 404
- [ ] `POST /jobs/{id}/confirm`：job 属于其他用户返回 403
- [ ] `POST /jobs/{id}/confirm`：job.status 不为 `awaiting_confirm` 返回 409
- [ ] `POST /jobs/{id}/confirm`：空 payload 正常通过（保留 LLM 结果），status 变为 `awaiting_directions`
- [ ] `POST /jobs/{id}/confirm`：带修正字段，DB 对应字段已更新
- [ ] `POST /jobs/{id}/reparse`：status 回退到 parsing，task_parse_jd.delay 被调用
- [ ] `POST /jobs/{id}/reparse`：feedback 传入后注入 LLM prompt
- [ ] `POST /jobs/{id}/directions`：LLM 返回 3-5 个建议方向
- [ ] `POST /jobs/{id}/directions`：带 feedback 换一批，方向列表随反馈变化
- [ ] `POST /jobs/{id}/start`：`selected_directions=[]` 返回 422
- [ ] `POST /jobs/{id}/start`：job.status 不为 `awaiting_directions` 返回 409
- [ ] `POST /jobs/{id}/start`：正常请求 status 变为 `researching`，`selected_directions` 已写入 DB
- [ ] `POST /jobs/{id}/start`：`task_run_research.delay` 被调用
