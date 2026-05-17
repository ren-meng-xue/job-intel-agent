# 前后端错误处理健全化 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为前后端建立统一的错误码体系、结构化错误响应、路由守卫、自定义 404 页面，让前端能根据错误码做精确分支处理。

**Architecture:** 后端引入 `AppError` 异常类和 `ErrorCode` 枚举，所有 API 层/Service 层统一抛 `AppError`；FastAPI 异常处理器将 `AppError` 和 `HTTPException` 都转为统一的 `ErrorResponse` JSON 格式 `{code, message, detail}`。前端 `http.ts` 解析结构化错误，`api.ts` 抛出带 code 的 `ApiError`；新增 `middleware.ts` 实现服务端路由守卫，`not-found.tsx` 处理 404。

**Tech Stack:** FastAPI + Pydantic（后端），Next.js 14 App Router + TypeScript（前端）

---

## File Structure

| 文件 | 操作 | 职责 |
|---|---|---|
| `backend/app/core/errors.py` | **Create** | `ErrorCode` 枚举 + `AppError` 异常类 |
| `backend/app/schemas/common.py` | **Create** | `ErrorResponse` Pydantic 模型 |
| `backend/app/main.py` | **Modify** | 注册 `AppError` 处理器 + 404 catch-all handler |
| `backend/app/services/auth_service.py` | **Modify** | `HTTPException` → `AppError` |
| `backend/app/api/v1/auth.py` | **Modify** | `HTTPException` → `AppError` |
| `backend/app/api/v1/jobs.py` | **Modify** | `HTTPException` → `AppError` |
| `backend/app/api/v1/reports.py` | **Modify** | `HTTPException` → `AppError` |
| `backend/app/api/v1/resume.py` | **Modify** | `HTTPException` → `AppError` |
| `backend/app/tasks/research.py` | **Modify** | error 事件带上 code + message |
| `frontend/src/lib/types.ts` | **Modify** | 新增 `ApiError` 类型 |
| `frontend/src/lib/errors.ts` | **Create** | `ApiError` 类 + `handleApiError` 工具函数 |
| `frontend/src/lib/http.ts` | **Modify** | 解析结构化错误响应，抛出 `ApiError` |
| `frontend/src/lib/api.ts` | **Modify** | 使用 `ApiError`，ResearchingCard 的 SSE 改用 `streamReport` |
| `frontend/src/middleware.ts` | **Create** | 服务端路由守卫，检查 refresh_token cookie |
| `frontend/src/app/not-found.tsx` | **Create** | 自定义 404 页面 |
| `frontend/src/app/error.tsx` | **Create** | 全局错误边界 |
| `frontend/src/components/report/ResearchingCard.tsx` | **Modify** | 改用 `streamReport()` 而非裸 EventSource |
| `frontend/src/components/AuthGuard.tsx` | **Modify** | 配合 middleware，简化客户端守卫逻辑 |

---

### Task 1: 后端 — 错误码枚举与 AppError 异常类

**Files:**
- Create: `backend/app/core/errors.py`

- [ ] **Step 1: 创建 `errors.py`**

```python
"""统一错误码体系。所有 API / Service 层通过 AppError 抛出结构化错误。"""

from enum import Enum


class ErrorCode(str, Enum):
    """业务错误码，前端据此做分支处理"""
    # ---- 认证 ----
    AUTH_TOKEN_MISSING = "AUTH_TOKEN_MISSING"
    AUTH_TOKEN_INVALID = "AUTH_TOKEN_INVALID"
    AUTH_TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED"
    AUTH_REFRESH_INVALID = "AUTH_REFRESH_INVALID"
    AUTH_CREDENTIALS_WRONG = "AUTH_CREDENTIALS_WRONG"

    # ---- 资源 ----
    NOT_FOUND = "NOT_FOUND"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    ACCESS_DENIED = "ACCESS_DENIED"

    # ---- 业务 ----
    CONFLICT = "CONFLICT"
    BAD_REQUEST = "BAD_REQUEST"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    RATE_LIMITED = "RATE_LIMITED"

    # ---- 服务端 ----
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UPSTREAM_ERROR = "UPSTREAM_ERROR"


# ErrorCode → HTTP status code 映射
_ERROR_CODE_STATUS: dict[ErrorCode, int] = {
    ErrorCode.AUTH_TOKEN_MISSING: 401,
    ErrorCode.AUTH_TOKEN_INVALID: 401,
    ErrorCode.AUTH_TOKEN_EXPIRED: 401,
    ErrorCode.AUTH_REFRESH_INVALID: 401,
    ErrorCode.AUTH_CREDENTIALS_WRONG: 401,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.ALREADY_EXISTS: 409,
    ErrorCode.ACCESS_DENIED: 403,
    ErrorCode.CONFLICT: 409,
    ErrorCode.BAD_REQUEST: 400,
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.UPSTREAM_ERROR: 502,
}


class AppError(Exception):
    """携带 ErrorCode 的异常，由 FastAPI exception handler 统一转换为 ErrorResponse"""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        detail: dict | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.detail = detail or {}
        self.status_code = _ERROR_CODE_STATUS.get(code, 500)
        super().__init__(message)
```

- [ ] **Step 2: 验证文件语法**

```bash
cd backend && uv run python -c "from app.core.errors import AppError, ErrorCode; e = AppError(ErrorCode.NOT_FOUND, 'xxx'); assert e.status_code == 404; print('OK')"
```

---

### Task 2: 后端 — ErrorResponse Schema

**Files:**
- Create: `backend/app/schemas/common.py`

- [ ] **Step 1: 创建 `common.py`**

```python
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """统一错误响应格式"""
    code: str
    message: str
    detail: dict | None = None
```

- [ ] **Step 2: 验证导入**

```bash
cd backend && uv run python -c "from app.schemas.common import ErrorResponse; print('OK')"
```

---

### Task 3: 后端 — main.py 注册异常处理器 + 404 catch-all

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: 重写 `main.py` 异常处理部分**

`main.py` 完整替换为：

```python
import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.schemas.common import ErrorResponse

logger = logging.getLogger(__name__)

app = FastAPI(title="Job Intel Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router, prefix="/api/v1")


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning("AppError: %s %s — %s: %s", request.method, request.url, exc.code.value, exc.message)
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            code=exc.code.value,
            message=exc.message,
            detail=exc.detail or None,
        ).model_dump(),
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code_map: dict[int, ErrorCode] = {
        400: ErrorCode.BAD_REQUEST,
        401: ErrorCode.AUTH_TOKEN_INVALID,
        403: ErrorCode.ACCESS_DENIED,
        404: ErrorCode.NOT_FOUND,
        409: ErrorCode.CONFLICT,
        422: ErrorCode.VALIDATION_ERROR,
        429: ErrorCode.RATE_LIMITED,
    }
    code = code_map.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            code=code.value,
            message=str(exc.detail),
        ).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            code=ErrorCode.VALIDATION_ERROR.value,
            message="请求参数校验失败",
            detail={"errors": exc.errors()},
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception: %s %s", request.method, request.url)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            code=ErrorCode.INTERNAL_ERROR.value,
            message="服务器内部错误",
        ).model_dump(),
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


# catch-all 路由：匹配所有未注册的 /api/v1/* 路径，返回结构化 404
@app.api_route("/api/v1/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def api_not_found(request: Request, path: str):
    return JSONResponse(
        status_code=404,
        content=ErrorResponse(
            code=ErrorCode.NOT_FOUND.value,
            message=f"接口不存在: /api/v1/{path}",
        ).model_dump(),
    )
```

- [ ] **Step 2: 启动后端验证无语法错误**

```bash
cd backend && uv run python -c "from app.main import app; print('OK')"
```

---

### Task 4: 后端 — 替换所有 HTTPException 为 AppError

**Files:**
- Modify: `backend/app/services/auth_service.py`
- Modify: `backend/app/api/v1/auth.py`
- Modify: `backend/app/api/v1/jobs.py`
- Modify: `backend/app/api/v1/reports.py`
- Modify: `backend/app/api/v1/resume.py`

- [ ] **Step 1: `auth_service.py` — 替换所有 HTTPException**

所有 `raise HTTPException(status_code=xxx, detail="...")` 替换为 `raise AppError(ErrorCode.XXX, "...")`：

```python
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AppError, ErrorCode
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.user import User
from app.repositories.auth_repository import AuthRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginResponse


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.user_repo = UserRepository(db)
        self.auth_repo = AuthRepository(db)

    async def register(self, email: str, username: str, password: str) -> User:
        if await self.user_repo.get_by_email(email):
            raise AppError(ErrorCode.ALREADY_EXISTS, "邮箱已被注册")
        if await self.user_repo.get_by_username(username):
            raise AppError(ErrorCode.ALREADY_EXISTS, "用户名已被占用")
        password_hash = hash_password(password)
        return await self.user_repo.create_user(email, username, password_hash)

    async def login(self, email: str, password: str) -> tuple[LoginResponse, str]:
        user = await self.user_repo.get_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            raise AppError(ErrorCode.AUTH_CREDENTIALS_WRONG, "邮箱或密码错误")
        access_token = create_access_token({"sub": user.id})
        refresh_token_plain = generate_refresh_token()
        expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        await self.auth_repo.create_session(user.id, hash_token(refresh_token_plain), expires_at)
        response = LoginResponse(
            access_token=access_token,
            user_id=user.id,
            email=user.email,
            username=user.username,
        )
        return response, refresh_token_plain

    async def refresh(self, refresh_token_plain: str) -> str:
        token_hash = hash_token(refresh_token_plain)
        auth_session = await self.auth_repo.get_active_session(token_hash)
        if not auth_session:
            raise AppError(ErrorCode.AUTH_REFRESH_INVALID, "refresh token 无效或已过期")
        user = await self.user_repo.get_by_id(auth_session.user_id)
        if not user:
            raise AppError(ErrorCode.AUTH_TOKEN_INVALID, "用户不存在")
        return create_access_token({"sub": user.id})

    async def logout(self, refresh_token_plain: str) -> None:
        token_hash = hash_token(refresh_token_plain)
        auth_session = await self.auth_repo.get_active_session(token_hash)
        if auth_session:
            await self.auth_repo.revoke_session(auth_session.id)


async def get_user_by_raw_token(token: str, db: AsyncSession) -> User:
    payload = decode_access_token(token)
    if not payload:
        raise AppError(ErrorCode.AUTH_TOKEN_INVALID, "token 无效或已过期")
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(payload["sub"])
    if not user:
        raise AppError(ErrorCode.AUTH_TOKEN_INVALID, "用户不存在")
    return user


async def get_current_user(
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise AppError(ErrorCode.AUTH_TOKEN_MISSING, "未提供认证 token")
    return await get_user_by_raw_token(authorization[7:], db)
```

- [ ] **Step 2: `auth.py` — 替换 HTTPException**

```python
# auth.py 第 55 行，仅一处需改：refresh_token 中未找到 cookie
# 把 raise HTTPException(status_code=401, detail="未找到 refresh token")
# 替换为：
raise AppError(ErrorCode.AUTH_TOKEN_MISSING, "未找到 refresh token")
```

在文件头部将 `from fastapi import APIRouter, Depends, HTTPException, Request, Response` 去掉 `HTTPException`，加上 `from app.core.errors import AppError, ErrorCode`。

- [ ] **Step 3: `jobs.py` — 替换所有 HTTPException**

所有 pattern 替换：

| 原 | 新 |
|---|---|
| `raise HTTPException(status_code=404, detail="Job not found")` | `raise AppError(ErrorCode.NOT_FOUND, "Job 不存在")` |
| `raise HTTPException(status_code=403, detail="Access denied")` | `raise AppError(ErrorCode.ACCESS_DENIED, "无权访问此 Job")` |
| `raise HTTPException(status_code=409, detail=f"Job status is '{job.status}', expected 'xxx'")` | `raise AppError(ErrorCode.CONFLICT, f"Job 当前状态为 '{job.status}'，不支持此操作")` |
| `raise HTTPException(status_code=422, detail="action 须为 approve / edit / retry")` | `raise AppError(ErrorCode.VALIDATION_ERROR, "action 须为 approve / edit / retry")` |

去掉 `from fastapi import APIRouter, Depends, HTTPException` 中的 `HTTPException`，加上 `from app.core.errors import AppError, ErrorCode`。

- [ ] **Step 4: `reports.py` — 替换所有 HTTPException**

| 原 | 新 |
|---|---|
| `raise HTTPException(status_code=401, detail="未提供认证 token")` | `raise AppError(ErrorCode.AUTH_TOKEN_MISSING, "未提供认证 token")` |
| `raise HTTPException(status_code=404, detail="Job not found")` | `raise AppError(ErrorCode.NOT_FOUND, "Job 不存在")` |
| `raise HTTPException(status_code=403, detail="Access denied")` | `raise AppError(ErrorCode.ACCESS_DENIED, "无权访问此 Job")` |
| `raise HTTPException(status_code=404, detail="Report not found")` | `raise AppError(ErrorCode.NOT_FOUND, "Report 不存在")` |

去掉 `HTTPException` import，加上 `from app.core.errors import AppError, ErrorCode`。

- [ ] **Step 5: `resume.py` — 替换所有 HTTPException**

| 原 | 新 |
|---|---|
| `raise HTTPException(409, "已有简历，请先删除后再上传")` | `raise AppError(ErrorCode.ALREADY_EXISTS, "已有简历，请先删除后再上传")` |
| `raise HTTPException(400, "仅支持 PDF 或 DOCX 格式")` | `raise AppError(ErrorCode.BAD_REQUEST, "仅支持 PDF 或 DOCX 格式")` |
| `raise HTTPException(413, "文件超过 10 MB 限制")` | `raise AppError(ErrorCode.BAD_REQUEST, "文件超过 10 MB 限制")` |
| `raise HTTPException(400, str(e))` | `raise AppError(ErrorCode.BAD_REQUEST, str(e))` |
| `raise HTTPException(404, "尚未上传简历")` | `raise AppError(ErrorCode.NOT_FOUND, "尚未上传简历")` |
| `raise HTTPException(404, "简历不存在")` | `raise AppError(ErrorCode.NOT_FOUND, "简历不存在")` |
| `raise HTTPException(403, "无权访问")` | `raise AppError(ErrorCode.ACCESS_DENIED, "无权访问此简历")` |

去掉 `HTTPException` import，加上 `from app.core.errors import AppError, ErrorCode`。

- [ ] **Step 6: 启动后端确认无导入错误**

```bash
cd backend && uv run python -c "from app.main import app; print('OK')"
```

---

### Task 5: 后端 — research.py 任务错误事件带上 code

**Files:**
- Modify: `backend/app/tasks/research.py`

- [ ] **Step 1: `_do_parse_jd` 的 except 块增加 code 字段**

`research.py:66-73` 处，把：

```python
    except Exception:
        async with AsyncSessionLocal() as session:
            repo = JobRepository(session)
            await repo.update_status(job_id, "failed")
        await redis.publish(
            f"job:{job_id}",
            json.dumps({"type": "error", "job_id": job_id}),
        )
```

改为：

```python
    except Exception as e:
        async with AsyncSessionLocal() as session:
            repo = JobRepository(session)
            await repo.update_status(job_id, "failed")
        await redis.publish(
            f"job:{job_id}",
            json.dumps({
                "type": "error",
                "job_id": job_id,
                "code": "UPSTREAM_ERROR",
                "message": "JD 解析失败，请稍后重试",
            }),
        )
```

- [ ] **Step 2: `_do_run_research` 的 except Exception 块增加 code 字段**

`research.py:189-196` 处，把：

```python
    except Exception:
        await redis.publish(
            f"job:{job_id}",
            json.dumps({"type": "error", "job_id": job_id}),
        )
        async with AsyncSessionLocal() as session:
            repo = JobRepository(session)
            await repo.update_status(job_id, "failed")
```

改为：

```python
    except Exception:
        await redis.publish(
            f"job:{job_id}",
            json.dumps({
                "type": "error",
                "job_id": job_id,
                "code": "INTERNAL_ERROR",
                "message": "调研任务异常，请稍后重试",
            }),
        )
        async with AsyncSessionLocal() as session:
            repo = JobRepository(session)
            await repo.update_status(job_id, "failed")
```

- [ ] **Step 3: 验证语法**

```bash
cd backend && uv run python -c "from app.tasks.research import task_parse_jd, task_run_research; print('OK')"
```

---

### Task 6: 前端 — 类型定义与 ApiError 类

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Create: `frontend/src/lib/errors.ts`

- [ ] **Step 1: `types.ts` 新增 ErrorCode 类型**

在 `types.ts` 末尾追加：

```typescript
// ---- 错误码 ----
export type ErrorCode =
  | 'AUTH_TOKEN_MISSING'
  | 'AUTH_TOKEN_INVALID'
  | 'AUTH_TOKEN_EXPIRED'
  | 'AUTH_REFRESH_INVALID'
  | 'AUTH_CREDENTIALS_WRONG'
  | 'NOT_FOUND'
  | 'ALREADY_EXISTS'
  | 'ACCESS_DENIED'
  | 'CONFLICT'
  | 'BAD_REQUEST'
  | 'VALIDATION_ERROR'
  | 'RATE_LIMITED'
  | 'INTERNAL_ERROR'
  | 'UPSTREAM_ERROR'

export interface ErrorResponseBody {
  code: ErrorCode
  message: string
  detail?: Record<string, unknown> | null
}
```

- [ ] **Step 2: 创建 `errors.ts`**

```typescript
import type { ErrorCode, ErrorResponseBody } from './types'

export class ApiError extends Error {
  code: ErrorCode
  status: number
  detail: Record<string, unknown> | null

  constructor(status: number, body: ErrorResponseBody) {
    super(body.message)
    this.name = 'ApiError'
    this.code = body.code
    this.status = status
    this.detail = body.detail ?? null
  }

  get isAuthError(): boolean {
    return this.code.startsWith('AUTH_')
  }

  get isNotFound(): boolean {
    return this.code === 'NOT_FOUND'
  }
}

export async function parseApiError(res: Response): Promise<ApiError> {
  let body: ErrorResponseBody = {
    code: 'INTERNAL_ERROR',
    message: `请求失败 (${res.status})`,
  }
  try {
    const json = await res.json()
    if (json.code && json.message) {
      body = json as ErrorResponseBody
    } else if (json.detail) {
      body.message = typeof json.detail === 'string' ? json.detail : JSON.stringify(json.detail)
    }
  } catch {
    // 无法解析 JSON 时使用默认 body
  }
  return new ApiError(res.status, body)
}
```

---

### Task 7: 前端 — http.ts 使用 ApiError

**Files:**
- Modify: `frontend/src/lib/http.ts`

- [ ] **Step 1: 重写 `http.ts`**

```typescript
import { ApiError, parseApiError } from './errors'
import { clearSession, getAccessToken, setSessionTokens } from './session'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1'
const TIMEOUT_MS = 30_000

async function doRefresh(): Promise<string | null> {
  const res = await fetch(`${BASE_URL}/auth/refresh-token`, {
    method: 'POST',
    credentials: 'include',
  })
  if (!res.ok) return null
  const data = (await res.json()) as { access_token: string }
  setSessionTokens(data.access_token)
  return data.access_token
}

function redirectToLogin(): void {
  clearSession()
  if (typeof window !== 'undefined') {
    window.location.replace('/auth')
  }
}

export async function http(path: string, init: RequestInit = {}): Promise<Response> {
  const token = getAccessToken()
  const headers = new Headers(init.headers as HeadersInit)

  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS)
  const signal = init.signal ? init.signal : controller.signal

  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers,
      credentials: 'include',
      signal,
    })

    if (res.status !== 401) return res

    // 401：尝试刷新，失败则清 session 并跳转登录
    const newToken = await doRefresh()
    if (!newToken) {
      redirectToLogin()
      throw await parseApiError(res)
    }

    headers.set('Authorization', `Bearer ${newToken}`)
    const retried = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers,
      credentials: 'include',
      signal,
    })

    if (retried.status === 401) {
      redirectToLogin()
      throw await parseApiError(retried)
    }
    return retried
  } catch (err) {
    if (err instanceof ApiError) throw err
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new ApiError(408, { code: 'INTERNAL_ERROR', message: '请求超时' })
    }
    throw new ApiError(0, { code: 'INTERNAL_ERROR', message: '网络错误，请检查连接' })
  } finally {
    clearTimeout(timeoutId)
  }
}
```

---

### Task 8: 前端 — api.ts 统一使用 streamReport + 抛出 ApiError

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: 重写 `api.ts`**

```typescript
import { ApiError, parseApiError } from './errors'
import { getAccessToken, clearSession } from './session'
import { http } from './http'
import type { ReportResponse } from './types'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1'

async function checkOk(res: Response): Promise<Response> {
  if (!res.ok) throw await parseApiError(res)
  return res
}

export async function createJob(url: string): Promise<{ id: string }> {
  const res = await checkOk(
    await http('/jobs', { method: 'POST', body: JSON.stringify({ url }) })
  )
  return res.json() as Promise<{ id: string }>
}

export async function uploadResume(file: File): Promise<{ id: string }> {
  const form = new FormData()
  form.append('file', file)
  const res = await checkOk(await http('/resume', { method: 'POST', body: form }))
  return res.json() as Promise<{ id: string }>
}

export async function confirmJob(
  jobId: string,
  data: { title: string; company: string; requirements: string[] }
): Promise<void> {
  await checkOk(
    await http(`/jobs/${jobId}/confirm`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  )
}

export async function startResearch(
  jobId: string,
  selectedDirections: string[]
): Promise<void> {
  await checkOk(
    await http(`/jobs/${jobId}/start`, {
      method: 'POST',
      body: JSON.stringify({ selected_directions: selectedDirections }),
    })
  )
}

export function streamReport(
  reportId: string,
  onEvent: (e: MessageEvent) => void,
  onError?: (error: ApiError) => void
): EventSource {
  const token = getAccessToken()
  const url = new URL(`${BASE_URL}/reports/${reportId}/stream`)
  if (token) url.searchParams.set('token', token)

  const es = new EventSource(url.toString())
  es.onmessage = onEvent
  es.onerror = () => {
    es.close()
    if (onError) {
      onError(new ApiError(401, { code: 'AUTH_TOKEN_INVALID', message: 'SSE 连接鉴权失败' }))
    } else {
      clearSession()
      if (typeof window !== 'undefined') window.location.replace('/auth')
    }
  }
  return es
}

export async function fetchReport(reportId: string): Promise<ReportResponse> {
  const res = await checkOk(await http(`/reports/${reportId}`))
  return res.json()
}
```

---

### Task 9: 前端 — 修复 ResearchingCard 使用 streamReport

**Files:**
- Modify: `frontend/src/components/report/ResearchingCard.tsx`
- Modify: `frontend/src/app/report/[id]/page.tsx`

- [ ] **Step 1: `ResearchingCard.tsx` — 用 `streamReport()` 替代裸 EventSource**

把 `ResearchingCard.tsx:21` 的：

```typescript
const es = new EventSource(`/api/v1/reports/${reportId}/stream`)
```

替换为从 `@/lib/api` 导入 `streamReport` 并使用：

```typescript
import { streamReport } from '@/lib/api'

// useEffect 中：
const es = streamReport(
  reportId,
  (e) => {
    // 原有的 onmessage 逻辑保持不变
    let data: { step?: string } = {}
    try { data = JSON.parse(e.data) } catch { return }
    // ... 其余保持不变
  },
  () => {
    // onError: SSE 断连时静默关闭（非鉴权问题，因为走 streamReport 鉴权已内置）
    // 如果需跳登录，streamReport 内部已处理
  }
)
```

完整替换后的 `ResearchingCard.tsx`：

```typescript
'use client'
import { useEffect, useState } from 'react'
import { streamReport } from '@/lib/api'

interface ProgressItem {
  direction: string
  status: 'pending' | 'running' | 'done'
}

interface Props {
  reportId: string
  directions: string[]
  onDone: () => void
}

export default function ResearchingCard({ reportId, directions, onDone }: Props) {
  const [items, setItems] = useState<ProgressItem[]>(
    directions.map((d) => ({ direction: d, status: 'pending' }))
  )

  useEffect(() => {
    const es = streamReport(
      reportId,
      (e) => {
        let data: { step?: string; type?: string } = {}
        try {
          data = JSON.parse(e.data)
        } catch {
          return
        }
        const step = data.step || ''

        if (step === 'done' || data.type === 'completed') {
          setItems((prev) => prev.map((i) => ({ ...i, status: 'done' })))
          es.close()
          onDone()
          return
        }

        setItems((prev) => {
          const matchIdx = directions.findIndex((d) => step.includes(d))
          return prev.map((item, i) => {
            if (matchIdx >= 0 && i === matchIdx) return { ...item, status: 'running' }
            if (matchIdx >= 0 && i < matchIdx) return { ...item, status: 'done' }
            return item
          })
        })
      }
      // onError 不传，让 streamReport 内部处理 401 → 跳登录
    )
    return () => es.close()
  }, [reportId, directions, onDone])

  return (
    <div className="space-y-2 text-sm">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-2 h-2 rounded-full bg-blue-600 animate-dot-pulse" />
        <p className="font-semibold text-gray-800">调研 &amp; 报告生成中…</p>
        <span className="ml-auto text-xs text-gray-400">预计 3-5 分钟</span>
      </div>
      {items.map((item, i) => (
        <div key={i} className="flex items-center gap-2.5">
          {item.status === 'done' && (
            <div className="w-4 h-4 rounded-full bg-green-500 flex items-center justify-center text-white text-xs flex-shrink-0">
              ✓
            </div>
          )}
          {item.status === 'running' && (
            <div className="w-4 h-4 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
              <div className="w-2 h-2 rounded-full bg-blue-600 animate-dot-pulse" />
            </div>
          )}
          {item.status === 'pending' && (
            <div className="w-4 h-4 rounded-full bg-gray-200 flex-shrink-0" />
          )}
          <span
            className={
              item.status === 'pending'
                ? 'text-gray-400'
                : item.status === 'running'
                ? 'text-gray-800 font-medium'
                : 'text-gray-600'
            }
          >
            {item.direction}
          </span>
          {item.status === 'running' && (
            <span className="ml-auto text-xs text-blue-500">搜索中…</span>
          )}
          {item.status === 'done' && (
            <span className="ml-auto text-xs text-green-500">完成</span>
          )}
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 2: `report/[id]/page.tsx` — 更新 SSE error handler 签名**

`page.tsx:85` 行的 SSE onError 回调签名不变（`onError` 第一个参数现在是 `onError?: (error: ApiError) => void`，但 `streamReport` 调用时可以不传 onError，让默认行为处理。当前代码传了 `() => router.replace('/auth')`，保持兼容即可，因为 `ApiError` 参数是可选的。

---

### Task 10: 前端 — middleware.ts 服务端路由守卫

**Files:**
- Create: `frontend/src/middleware.ts`

- [ ] **Step 1: 创建 `middleware.ts`**

```typescript
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

const AUTH_ROUTES = ['/auth']
const PUBLIC_EXTENSIONS = /\.(ico|png|svg|jpg|jpeg|gif|css|js|woff2?)$/

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // 静态资源放行
  if (PUBLIC_EXTENSIONS.test(pathname)) return NextResponse.next()

  // auth 页面放行
  if (AUTH_ROUTES.some((r) => pathname.startsWith(r))) return NextResponse.next()

  // 检查 refresh_token cookie 是否存在
  const refreshToken = request.cookies.get('refresh_token')
  if (!refreshToken?.value) {
    const loginUrl = new URL('/auth', request.url)
    loginUrl.searchParams.set('redirect', pathname)
    return NextResponse.redirect(loginUrl)
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|api|favicon.ico).*)'],
}
```

---

### Task 11: 前端 — not-found.tsx 自定义 404 页面

**Files:**
- Create: `frontend/src/app/not-found.tsx`

- [ ] **Step 1: 创建 `not-found.tsx`**

```typescript
import Link from 'next/link'

export default function NotFound() {
  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <h1 className="text-6xl font-bold text-gray-200 mb-4">404</h1>
        <p className="text-lg text-gray-600 mb-2">页面未找到</p>
        <p className="text-sm text-gray-400 mb-8">你访问的路径不存在，请检查 URL 是否正确</p>
        <Link
          href="/"
          className="inline-block rounded-lg bg-blue-600 px-6 py-2.5 text-white font-medium hover:bg-blue-700 transition-colors"
        >
          返回首页
        </Link>
      </div>
    </main>
  )
}
```

---

### Task 12: 前端 — error.tsx 全局错误边界

**Files:**
- Create: `frontend/src/app/error.tsx`

- [ ] **Step 1: 创建 `error.tsx`**

```typescript
'use client'

import { useEffect } from 'react'

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error('Unhandled page error:', error)
  }, [error])

  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center max-w-md">
        <h1 className="text-4xl font-bold text-gray-200 mb-4">出错了</h1>
        <p className="text-gray-600 mb-2">页面遇到了未预期的错误</p>
        <p className="text-xs text-gray-400 mb-8 font-mono break-all">
          {error.message || '未知错误'}
        </p>
        <button
          onClick={reset}
          className="inline-block rounded-lg bg-blue-600 px-6 py-2.5 text-white font-medium hover:bg-blue-700 transition-colors"
        >
          重试
        </button>
      </div>
    </main>
  )
}
```

---

### Task 13: 前端 — AuthGuard 配合 middleware 简化

**Files:**
- Modify: `frontend/src/components/AuthGuard.tsx`

- [ ] **Step 1: 简化 AuthGuard（middleware 已做 cookie 检查）**

```typescript
'use client'

import { useEffect, useState } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { getAccessToken } from '../lib/session'

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()
  const [ready, setReady] = useState(false)

  useEffect(() => {
    if (pathname?.startsWith('/auth')) {
      setReady(true)
      return
    }
    // middleware 已检查 refresh_token cookie，这里只需验证 access_token
    if (!getAccessToken()) {
      router.replace('/auth')
    } else {
      setReady(true)
    }
  }, [pathname, router])

  if (!ready) return null
  return <>{children}</>
}
```

逻辑不变，仅加注释说明 middleware 的职责分工。

---

### Task 14: 验证 — 端到端检查

- [ ] **Step 1: 启动后端，用 curl 测试错误码**

```bash
# 终端 1：
cd backend && uv run uvicorn app.main:app --reload --port 8000

# 终端 2：
# 测试 401 未认证
curl -s http://localhost:8000/api/v1/auth/me | python3 -m json.tool
# 预期: {"code": "AUTH_TOKEN_MISSING", "message": "未提供认证 token", "detail": null}

# 测试 404 接口不存在
curl -s http://localhost:8000/api/v1/nonexistent | python3 -m json.tool
# 预期: {"code": "NOT_FOUND", "message": "接口不存在: /api/v1/nonexistent", "detail": null}

# 测试 404 资源不存在
# (需带有效 token，此处只验证格式)
curl -s -H "Authorization: Bearer fake" http://localhost:8000/api/v1/jobs/nonexist/confirm -X POST -H "Content-Type: application/json" -d '{"title":"t","company":"c","requirements":[]}' | python3 -m json.tool
# 预期: {"code": "AUTH_TOKEN_INVALID", "message": "token 无效或已过期", "detail": null}
```

- [ ] **Step 2: 启动前端，验证路由守卫和 404**

```bash
cd frontend && pnpm dev
```

验证项：
1. 未登录访问 `/` → 重定向到 `/auth`
2. 未登录访问 `/auth` → 正常显示登录页
3. 访问不存在的路径 `/xyz` → 显示自定义 404 页面
4. 登录后，后端 API 返回结构化错误时，浏览器 console 无未捕获异常

- [ ] **Step 3: 检查 TypeScript 编译**

```bash
cd frontend && pnpm tsc --noEmit
```
