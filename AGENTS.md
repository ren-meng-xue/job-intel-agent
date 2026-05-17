# Repository Guidelines

## 项目结构与模块组织
本仓库分为 `backend/` 和 `frontend/`。后端代码位于 `backend/app/`，按 `api/`、`services/`、`repositories/`、`models/`、`schemas/`、`tasks/`、`graphs/` 分层；后端测试位于 `backend/tests/`。前端代码位于 `frontend/src/`，路由在 `src/app/`，复用组件在 `src/components/`，工具与 API 客户端在 `src/lib/`、`src/services/`。文档、原型、脚本、日志和变更记录分别放在 `docs/`、`html/`、`scripts/`、`logs/`、`changelogs/`。

## 构建、测试与本地开发命令
- `./dev.sh`：启动 PostgreSQL、Redis、Alembic 迁移、FastAPI、Celery 和 Next.js，端口为 `8001`、`3001`。
- `cd backend && uv run pytest`：运行后端测试。
- `cd backend && uv run ruff check .`：运行 Python lint 和 import 排序检查。
- `cd backend && uv run uvicorn app.main:app --reload --port 8001`：仅启动后端。
- `cd backend && uv run celery -A app.tasks:celery_app worker --loglevel=info`：仅启动异步任务 worker。
- `cd frontend && pnpm dev --port 3001`：仅启动前端。
- `cd frontend && pnpm build`：构建前端生产包。
- `cd frontend && pnpm lint`：运行 Next.js lint 检查。
- `docker compose up -d postgres redis`：仅启动本地基础设施。

## 代码风格与命名约定
Python 使用 4 空格缩进、FastAPI/Pydantic 类型声明，并遵循 Ruff，最大行宽为 88。后端模块使用 snake_case，类名使用 PascalCase，文件按职责命名，例如 `resume_service.py`。前端使用 TypeScript，React 组件使用 PascalCase，例如 `ReportView.tsx`；工具函数、hooks、API 客户端使用 camelCase。路由文件保持精简，复用 UI 放入 `frontend/src/components/`。

## 测试规范
后端测试使用 `pytest` 和 `pytest-asyncio`，测试文件放在 `backend/tests/`，命名为 `test_<feature>.py`。涉及鉴权、解析、SSE、研究图、仓储层或错误处理的改动必须补充聚焦测试。当前没有独立前端测试套件，前端改动至少需要运行 `pnpm lint` 并手动验证受影响页面。

## 提交与 Pull Request 规范
提交历史使用简短前缀，例如 `feat:`、`chore:`、`merge:`。提交信息应描述清楚范围，例如 `feat: add resume parse endpoint`。PR 需要说明用户可见变化、涉及区域（`backend`、`frontend`、migration、worker 等）、关联文档或 issue；UI 改动附截图或录屏；新增环境变量、数据库迁移、后台任务影响必须单独说明。

## 安全与配置提示
本地配置从 `.env.example` 复制，密钥只放在 `.env`，不要提交日志、凭证或本地运行产物。修改数据库模型时，需要在 `backend/alembic/versions/` 添加迁移，并通过 `logs/backend.log`、`logs/celery.log` 验证启动状态。

## Agent 专用指令
每次回复用户都必须使用中文。删除任何文件、目录、数据、分支或远程资源前，必须先说明删除目标与影响范围，并等待用户明确允许后再执行。
