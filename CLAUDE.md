# Job Intel Agent — 主控规范

## 全局约束（始终生效，任何情况不可跳过）

1. 始终使用**简体中文**回复
2. 所有配置走环境变量，**禁止硬编码** Key / Secret
3. commit / push 规则：
   - 若用户消息**本身即为 commit/push 指令**（如「commit」「push」「commit+push」），直接执行
   - 若 commit/push 是 Claude **主动发起**，必须先说明将要提交的内容，等用户回复「**1**」后执行
   - push 完成后，若当前分支非 main/master，询问用户是否需要合并到 main
4. LLM 调用只在 `services/` 层，`api/` 层禁止直接调用
5. 实时状态用 SSE + Redis Pub/Sub，**禁止轮询**
6. 数据库变更必须走 Alembic，禁止直接改表结构；ORM 模型变更后的迁移步骤见 `.claude/skills/deploy.md`
7. 本地开发环境通过 `./dev.sh` 启动（混合模式：Docker 跑 postgres + redis，其余服务直接在本机跑）。新增或删除服务时，**必须同步更新 `dev.sh`**，保持脚本与实际架构一致
8. 会话开始 / 用户说「todo」时的流程、changelog 读写与更新规则，见 `.claude/skills/changelog.md`
9. 切换分支前，必须先执行 `git status` 检查未提交改动。如有，列出清单，询问用户：先 commit 再切，还是直接切
10. 开发顺序：先写实现代码，实现完成后再写测试并运行通过。不使用"先写失败测试"的 TDD 流程
11. **制定计划前必须执行分支检查**（触发时机：用户要求新功能/新 Phase/新模块，或 Claude 即将使用 `writing-plans` skill 时）：
    a. 执行 `git branch --show-current` — 获取当前分支名
    b. 判断本次计划内容是否为独立新功能（与当前分支职责无关的全新内容）
    c. 若属于新功能/新模块：询问用户「是否为此功能创建新分支？建议名称：`feature/xxx`」
    d. 执行 `git status` — 检查是否有未提交或已暂存的改动；若有，列出清单并询问：
       - 先 commit / stash 再切分支？
       - 还是留在当前分支继续？
    e. 等待用户回应（语义判断，不限固定词——「ok」「1」「好」等均视为同意），再开始制定计划
    f. 若当前在 `main` 且计划内容需要独立分支，必须提醒，不可直接在 `main` 开发

---

## Skill 路由表

遇到以下情境时，**主动读取**对应 Skill 文件，按其规范执行：

| 触发情境 | 读取 Skill |
|---|---|
| 讨论产品方向、功能边界、用户价值、竞品对比 | `.claude/skills/product.md` → 结合 `superpowers: brainstorming` |
| 开发新功能、新 API、新模块 | `.claude/skills/feature-dev.md` → 结合 `superpowers: writing-plans` |
| 修复 Bug、排查问题、分析报错 | `.claude/skills/bug-fix.md` → 结合 `gstack: /investigate` |
| 编写测试、输出测试报告 | `.claude/skills/testing.md` → 结合 `superpowers: tdd` + `gstack: /qa` |
| 前端 UI 开发、页面验证、设计审计 | `.claude/skills/frontend.md` → 结合 `gstack: /browse /qa /design-review` |
| 部署上线、环境配置、迁移 | `.claude/skills/deploy.md` → 结合 `gstack: /cso /ship` |
| 代码审查（任意场景） | `gstack: /review` |
| 并行子任务开发（多模块同步） | `superpowers: subagent-driven-development` |
| 写 changelog、读 changelog、更新进度 | `.claude/skills/changelog.md` |

---

## 技术栈（快速参考）

- 后端：FastAPI + **uvicorn**（ASGI）+ Celery + Redis + SQLAlchemy（异步）
- Agent 编排：**LangGraph**（多步调研 Agent 图、Human-in-the-Loop 节点）
- 前端：Next.js + TypeScript + Tailwind CSS
- LLM：`gpt-4o`（主推理）/ `gpt-4o-mini`（轻量任务）
- 爬取：Firecrawl | 搜索：Tavily API | 数据库：PostgreSQL + pgvector
- 包管理：**uv**（后端，Python 3.12，`pyproject.toml` + `uv sync`）/ **pnpm**（前端）；后端所有命令必须加 `uv run` 前缀（如 `uv run alembic`、`uv run pytest`），直接调用会因 pyenv 找不到 3.12 而报错
- 测试：**pytest** + pytest-asyncio + httpx
- 目录：`backend/`（FastAPI + Alembic）/ `frontend/`（Next.js）/ `dev.sh`（一键启动）
