# Job Intel Agent — 全局开发 Spec

> 创建时间：2026-05-14  
> 状态：待执行

---

## Context

这是一个面向求职者的 AI 情报助手。用户粘贴 JD 链接 + 上传简历，Agent 自主调研，3-5 分钟生成专属面试情报报告。项目目前只有架构脚手架，所有核心业务逻辑均为 `raise NotImplementedError`。本 spec 覆盖从零到完整可运行产品的全部实现任务。

**设计已决策（不再讨论）：**
- HiTL 用拆任务方案（不用 LangGraph interrupt）
- LangGraph 只用于 research 阶段的并行搜索图
- Auth 复用 offer-copilot 的 JWT + HttpOnly Cookie + AuthSession 模式
- 实时进度用 SSE + Redis Pub/Sub，禁止轮询

---

## 开发阶段与任务拆分

### Phase 1 — Auth（后端 + 前端）

**目标：** 可以注册、登录、登出，所有后续接口需要鉴权。

#### 1A. 后端 Auth

**新增文件：**
- `backend/app/models/user.py` — User 表（id, email, username, password_hash, status, email_verified, last_login_at, failed_login_count, locked_until）
- `backend/app/models/auth_session.py` — AuthSession 表（id, user_id FK, refresh_token_hash, expires_at, revoked_at）
- `backend/app/core/security.py` — bcrypt hash/verify, HS256 JWT create/decode, secrets refresh token, SHA256 hash
- `backend/app/schemas/auth.py` — LoginRequest, RegisterRequest, LoginResponse, UserInfoResponse
- `backend/app/repositories/user_repository.py` — get_by_id/email/username, create_user
- `backend/app/repositories/auth_repository.py` — create/get/update/revoke session
- `backend/app/services/auth_service.py` — register, login（返回 LoginResponse + refresh token 明文）, refresh, logout
- `backend/app/api/v1/auth.py`**** — POST /auth/login, /auth/register, /auth/refresh-token, /auth/logout, GET /auth/me

**修改文件：**
- `backend/app/models/__init__.py` — 导出 User, AuthSession
- `backend/app/api/v1/router.py` — 注册 auth 路由
- `backend/app/core/config.py` — 新增 SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_COOKIE_NAME 等配置
- `backend/app/api/v1/jobs.py`、`reports.py`、`resume.py` — 所有接口加 `current_user: User = Depends(get_current_user)` 鉴权依赖

**Alembic：**
- `alembic revision --autogenerate -m "add users and auth_sessions tables"`
- `alembic upgrade head`

**关键参考：** offer-copilot 的实现，直接复用相同结构和逻辑。

**依赖新增（pyproject.toml）：**
- `bcrypt>=5.0.0`
- `python-jose[cryptography]>=3.3.0`
- `email-validator>=2.2.0`

---

#### 1B. 前端 Auth

**目标：** 完全复刻 `ui-prototype.html` 的屏幕①（登录/注册），接入真实 Auth API。

**新增文件：**
- `frontend/src/app/auth/page.tsx` — 登录/注册页（复刻原型屏幕①，含左侧动画角色、右侧 Tab 表单）
- `frontend/src/lib/http.ts` — 统一 fetch 封装，自动 Bearer header，401 自动 refresh-token 重试
- `frontend/src/lib/session.ts` — localStorage 存 access token，HttpOnly cookie 存 refresh token，restoreSession, setSessionTokens, clearSession
- `frontend/src/components/AuthGuard.tsx` — 包裹需要保护的页面，启动时验证 session，未授权跳转 /auth
- `frontend/src/services/auth.ts` — login, register, logout, refreshToken API 调用

**修改文件：**
- `frontend/src/lib/api.ts` — 所有请求改走 http.ts（自动带 token）
- `frontend/src/app/layout.tsx` — 包裹 AuthGuard

**动画角色实现注意：**
- 原型中 4 个角色（橙色、紫色、深色、黄色）跟随鼠标移动眼球 + 随机眨眼
- 在 Next.js 中用 `useRef` + `useEffect` + `mousemove` 事件实现，逻辑参考原型 `initAuthCharacters()` JS

---

### Phase 2 — 核心 Pipeline（后端）

**目标：** 从提交 JD URL 到生成报告，完整后端链路可运行。

#### 2A. Job 解析任务（task_parse_jd）

**流程：**
```
POST /api/v1/jobs (url, resume_id?)
  → 创建 Job 记录（status=parsing）
  → 触发 Celery task: task_parse_jd.delay(job_id)
  → 返回 { id, status: "parsing" }

task_parse_jd(job_id):
  1. scrape_url(job.url) [Firecrawl] → raw_content
  2. LLM 提取结构化信息（title, company, requirements: List[str], summary）
  3. 更新 Job（raw_content, title, company, status="awaiting_confirm"）
  4. Redis Pub/Sub publish: channel=job:{job_id}  event={"type":"parsed","title":...,"company":...,"requirements":[...]}
```

**修改文件：**
- `backend/app/api/v1/jobs.py` — 实现 create_job
- `backend/app/tasks/research.py` — 新增 task_parse_jd（原 run_research 改名或拆分）
- `backend/app/services/llm_service.py` — 新增 extract_job_info(markdown) 方法（prompt: 从 JD 原文提取结构化字段）
- `backend/app/models/job.py` — 新增字段：user_id (FK users.id), resume_id (nullable), requirements (JSON/Text), jd_summary (Text), selected_directions (JSON), status 扩展为枚举

**Job status 枚举：**
`pending` → `parsing` → `awaiting_confirm` → `researching` → `awaiting_directions` → `generating` → `done` → `failed`

---

#### 2B. SSE 推送端点

**修改文件：**
- `backend/app/api/v1/reports.py` — 实现 `GET /reports/{job_id}/stream`

**实现逻辑：**
```python
async def stream_events(job_id: str):
    redis = await get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"job:{job_id}")
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                yield f"data: {message['data']}\n\n"
    finally:
        await pubsub.unsubscribe(f"job:{job_id}")
        await pubsub.close()

return StreamingResponse(stream_events(job_id), media_type="text/event-stream",
    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
```

---

#### 2C. HiTL 确认接口

**新增端点：**
- `POST /api/v1/jobs/{id}/confirm` — 用户确认 JD 信息（可修正 title/company/requirements）
- `POST /api/v1/jobs/{id}/start` — 用户选择调研方向后触发 task_run_research

**修改文件：**
- `backend/app/api/v1/jobs.py` — 新增 confirm_job, start_research

---

#### 2D. LangGraph 研究图（task_run_research）

**文件：**
- `backend/app/services/research_graph.py` — 定义 LangGraph 图

**AgentState：**
```python
class ResearchState(TypedDict):
    job_id: str
    job_title: str
    company: str
    requirements: list[str]
    resume_summary: str | None
    selected_directions: list[str]
    search_results: dict[str, list[dict]]  # direction → results
    report_modules: dict[str, str]         # module_name → content
```

**图结构：**
```
START
  └→ prepare_node（从 DB 加载 job/resume 信息）
  └→ [parallel_search_nodes]（Fan-out，按 selected_directions 动态并发）
       每个 node: search(query) → search_results[direction]
       SSE publish: {"type":"progress","step":"searching","direction":"公司近期动态"}
  └→ synthesis_node（LLM 汇总各方向搜索结果）
       SSE publish: {"type":"progress","step":"synthesizing"}
  └→ report_node（LLM 生成 6 模块结构化报告）
       SSE publish: {"type":"progress","step":"generating"}
  └→ save_node（写入 DB reports 表）
       SSE publish: {"type":"done","report_id":"..."}
END
```

**并行 Fan-out 实现：**
LangGraph 的 `Send` API 实现动态并行节点——根据 selected_directions 生成 N 个并发 search 边。

**修改文件：**
- `backend/app/tasks/research.py` — task_run_research 调用 research_graph.run()
- `backend/app/services/report_service.py` — 改为调用 research_graph
- `backend/pyproject.toml` — 新增 `langgraph>=0.2.0`, `langchain-openai>=0.1.0`

---

#### 2E. 简历解析

**修改文件：**
- `backend/app/api/v1/resume.py` — 实现文件上传，存本地（`/tmp/resumes/`），触发 task_parse_resume
- `backend/app/services/resume_service.py` — 实现 parse_resume（pdfplumber + docx2txt + LLM）
- `backend/app/models/resume.py` — Resume 表（id, user_id, filename, parsed_content JSON, status）
- `backend/app/tasks/research.py` — 新增 task_parse_resume

**新增依赖：**
- `pdfplumber>=0.10.0`
- `python-docx>=1.0.0`

**Resume 解析 LLM prompt 目标：** 提取 name, skills, experience(年限), projects(摘要列表), education

---

### Phase 3 — 前端完整复刻（屏幕 ② - ⑦）

**目标：** 完全按 `ui-prototype.html` 复刻所有屏幕，接入真实 API。

#### 屏幕结构与路由

| 屏幕 | 路由 | 组件文件 |
|---|---|---|
| ② 首页输入 | `/` | `app/page.tsx` + `components/JobInputForm.tsx` |
| ③-⑥ 流程页 | `/jobs/[id]` | `app/jobs/[id]/page.tsx` |
| ⑦ 报告页 | `/reports/[id]` | `app/reports/[id]/page.tsx` |

**流程页（/jobs/[id]）** 根据 job.status 渲染不同状态：
- `parsing` → 屏幕③（解析中，4阶段卡片，阶段1转圈）
- `awaiting_confirm` → 屏幕④（解锁确认卡片，可编辑 title/company/requirements tags）
- `researching` / `awaiting_directions` → 屏幕⑤（选择方向卡片）
- `generating` → 屏幕⑥（调研进行中，子任务逐条完成）
- `done` → 自动跳转到 `/reports/{report_id}`

**状态同步机制：**
- 每个阶段的页面通过 SSE（`EventSource /api/v1/reports/{job_id}/stream`）监听进度
- 收到 `parsed` 事件 → 渲染确认卡片
- 收到 `progress` 事件 → 更新调研进度列表
- 收到 `done` 事件 → 跳转报告页

#### 关键组件实现

**步骤进度条（Stepper）** — 4步，每步有 locked/active/done 三态，复刻原型 `renderStepper()`

**确认 JD 卡片（ConfirmCard）：**
- 可编辑 input（title, company）
- Tag 编辑器（点击删除 × ，回车添加），复刻原型 `addTag()` 和 `req-tags` 逻辑
- 确认按钮 → `POST /jobs/{id}/confirm`

**调研方向选择（DirectionSelector）：**
- 6 个卡片，默认全选，可反选（至少选1个）
- 复刻原型 `renderDirections()` + `toggleDir()`
- 开始按钮 → `POST /jobs/{id}/start`

**调研进度列表（ResearchProgress）：**
- 6 个子任务条目（pending → active → done 动画）
- SSE 每次 progress 事件更新对应条目状态

**报告页（ReportPage）** — 6 个模块卡片：
1. 职位解读（tag-hard/soft/hidden 标签 + 分析文本）
2. 简历匹配度（双列：优势 vs Gap）
3. 公司画像（文本 + 标签）
4. 面试题预测（折叠 Q&A，`toggleQA()` 展开答题思路）
5. 薪资参考（横轴区间条，range-fill 动画）
6. 备战建议（有序列表）

**新增前端依赖：**
- 暂无（保持轻量，不引入 react-query / zustand，用 useState + useEffect 管理）

---

### Phase 4 — 收尾与验证

- `GET /api/v1/jobs/{id}` — 查询 Job 状态（前端初始化时拉取当前状态）
- `GET /api/v1/reports/{id}` — 查询完整报告内容
- 错误处理：task 失败时更新 job.status=failed，SSE 推送 error 事件，前端显示失败状态卡片
- dev.sh 同步更新（如有新进程/服务）

---

## 关键文件路径速查

| 文件 | 用途 |
|---|---|
| `backend/app/core/security.py` | JWT / bcrypt / token hash（新增） |
| `backend/app/services/auth_service.py` | Auth 业务逻辑（新增） |
| `backend/app/services/research_graph.py` | LangGraph 研究图（新增） |
| `backend/app/services/llm_service.py` | LLM 调用封装（扩展） |
| `backend/app/tasks/research.py` | Celery 任务（扩展） |
| `backend/app/api/v1/jobs.py` | Job CRUD + HiTL 接口（实现） |
| `backend/app/api/v1/reports.py` | SSE 流 + 报告查询（实现） |
| `frontend/src/lib/http.ts` | HTTP 客户端（新增） |
| `frontend/src/lib/session.ts` | Token 管理（新增） |
| `frontend/src/app/auth/page.tsx` | 登录/注册页（新增） |
| `frontend/src/app/jobs/[id]/page.tsx` | 流程页（新增） |
| `frontend/src/app/reports/[id]/page.tsx` | 报告页（改造） |
| `ui-prototype.html` | UI 复刻参考源（只读） |

---

## 验证方法

1. `./dev.sh` 启动全栈，确认 health endpoint 正常
2. 浏览器访问 `http://localhost:3001`，看到登录页
3. 注册新用户，登录成功，跳转首页
4. 粘贴真实 Boss/拉勾 JD 链接，点开始分析
5. 看到解析中动画 → SSE 推送 → 确认卡片弹出
6. 确认职位信息，选择调研方向
7. 看到调研进度逐条完成
8. 报告页展示 6 个模块，内容针对该 JD
9. 刷新报告页，内容依然存在（非内存态）

---

## 执行顺序

```
Phase 1A（后端 Auth）
  ↓
Phase 1B（前端 Auth）  ← 可与 Phase 2A 并行
  ↓
Phase 2A（task_parse_jd + POST /jobs）
  ↓
Phase 2B（SSE 端点）
  ↓
Phase 2C（HiTL 确认接口）
  ↓
Phase 2D（LangGraph 研究图）
  ↓
Phase 2E（简历解析）← 可与 2D 并行
  ↓
Phase 3（前端全量复刻）
  ↓
Phase 4（收尾验证）
```

