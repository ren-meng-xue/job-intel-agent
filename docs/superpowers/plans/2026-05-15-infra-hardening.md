# 基础设施健全化 — 修复计划

**Goal:** 收口前后端基础设施机制，优先修复会导致任务丢失、越权访问、页面卡死、错误不可观测的问题，并恢复测试/lint 基线。

**Scope:** 只处理机制层问题，不改业务产品逻辑。覆盖错误规范、鉴权恢复、权限校验、SSE 契约、Celery 任务注册、日志、配置安全和质量门禁。

**Current Findings:**
- Celery worker 日志显示 `research.parse_jd`、`resume.parse` 未注册，异步任务会被丢弃。
- `GET /api/v1/reports/{report_id}` 只校验登录，未校验 report 归属。
- 后端解析事件发布 `type=parsed`，前端解析页等待 `hitl/parse_complete/confirm`，状态机可能卡住。
- 后台任务捕获异常后缺少 `logger.exception`，线上排障信息不足。
- 前端登录/注册未复用结构化错误解析，页面级 API 调用缺少错误态。
- 后端测试、Ruff、前端 lint 当前都不能作为稳定质量门禁。

---

## Task 1: P0 — 修复任务丢失、越权与状态机卡死

**Files:**
- Modify: `backend/app/tasks/__init__.py`
- Modify: `backend/app/api/v1/reports.py`
- Modify: `backend/app/tasks/research.py`
- Modify: `frontend/src/app/report/[id]/page.tsx`
- Modify: related tests

- [x] 修复 Celery task autodiscover/显式 import，确保 worker 注册 `research.parse_jd`、`research.run`、`resume.parse`。
- [x] 为报告详情接口补充 job 归属校验，非本人报告返回 `ACCESS_DENIED`。
- [x] 统一 JD 解析完成 SSE 事件契约，前端能从 `parsed` 进入确认步骤。
- [x] 增加/更新测试覆盖上述 3 个 P0 修复。

## Task 2: P1 — 错误处理与鉴权恢复闭环

**Files:**
- Modify: `frontend/src/services/auth.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/http.ts`
- Modify: `frontend/src/components/AuthGuard.tsx`
- Modify: `frontend/src/components/JobInputForm.tsx`
- Modify: `frontend/src/app/report/[id]/page.tsx`

- [x] 登录/注册改用 `parseApiError`，展示后端 `message`。
- [x] 页面级 API 调用补充错误态，避免静默失败和无限 loading。
- [ ] SSE `onerror` 不再一律判定为鉴权失败，区分网络/鉴权/服务端错误。
- [x] AuthGuard 在 access token 缺失但 refresh cookie 存在时尝试恢复会话。

## Task 3: P1 — 后台任务与外部服务可观测性

**Files:**
- Modify: `backend/app/tasks/research.py`
- Modify: `backend/app/tasks/resume.py`
- Modify: `backend/app/services/llm_service.py`
- Modify: `backend/app/services/crawler_service.py`
- Modify: `backend/app/services/search_service.py`

- [x] 后台任务异常分支增加 `logger.exception`，保留 job/resume id。
- [ ] 外部服务调用补充 timeout、错误映射和最小重试策略。
- [ ] Redis publish 失败时记录日志，避免吞掉任务失败信号。

## Task 4: P2 — 配置安全与质量门禁

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/api/v1/auth.py`
- Modify: `backend/app/main.py`
- Modify: `frontend/package.json` or ESLint config
- Modify: tests/lint targets as needed

- [ ] 生产环境禁止使用默认 `SECRET_KEY`，cookie `secure` 走环境变量。
- [ ] `/health` 扩展为 DB/Redis/Celery broker 健康检查。
- [x] 修复 pytest 失败断言，恢复 `uv run pytest` 基线。
- [ ] 配置前端 ESLint，避免 `pnpm lint` 进入交互初始化。
- [ ] 收敛 Ruff 检查范围或修复全量问题，恢复 `uv run ruff check .` 基线。

## Verification

- [x] `cd backend && uv run pytest`
- [ ] `cd backend && uv run ruff check .`
- [x] `cd frontend && pnpm exec tsc --noEmit`
- [x] `cd frontend && pnpm build`
- [ ] `cd frontend && pnpm lint`
- [ ] 启动 `./dev.sh` 后确认 Celery registered tasks 包含 3 个任务。
